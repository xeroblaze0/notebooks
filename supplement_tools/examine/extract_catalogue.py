#!/home/user/Projects/notebooks/.venv/bin/python
import sqlite3
import requests
from bs4 import BeautifulSoup
import re
import os
import time
from typing import Optional, Tuple, List, Dict, Any, Callable
from functools import wraps

DB_PATH = "/home/user/Projects/notebooks/supplement_tools/examine/examine_catalogue.db"


def retry_get(max_retries: int = 3, backoff_factor: float = 1.0) -> Callable:
    """
    Decorator to retry a requests call with exponential backoff.
    """
    def decorator(func: Callable) -> Callable:
        """
        Inner decorator function that applies the wrapper.
        """
        @wraps(func)
        def wrapper(url: str, *args: Any, **kwargs: Any) -> Any:
            """
            Wrapper function that attempts the request and handles retries upon failure.
            """
            last_err = None
            for att in range(max_retries):
                try:
                    response = func(url, *args, **kwargs)
                    response.raise_for_status()
                    return response
                except requests.RequestException as e:
                    last_err = e
                    print(f"Request failed: {e}. Retrying {att + 1}/{max_retries}...")
                    time.sleep(backoff_factor * (2 ** att))
            raise last_err
        return wrapper
    return decorator


@retry_get(max_retries=3, backoff_factor=2.0)
def fetch_url(url: str, headers: Dict[str, str], timeout: int) -> requests.Response:
    """Fetch a URL using requests, wrapped with retry logic."""
    return requests.get(url, headers=headers, timeout=timeout)


def init_db() -> None:
    """Initialize the database schema for the examine supplements."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS supplements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            url TEXT UNIQUE,
            overview TEXT,
            what_it_is TEXT,
            benefits TEXT,
            drawbacks TEXT,
            how_it_works TEXT,
            dosage TEXT,
            min_dose REAL,
            max_dose REAL,
            safety_summary TEXT,
            side_effects TEXT,
            interactions TEXT,
            nutrient_depletions TEXT,
            pregnancy_lactation TEXT,
            precautions TEXT
        )
    ''')
    conn.commit()
    conn.close()

def extract_dosage(dosage_text: str) -> Tuple[Optional[float], Optional[float]]:
    """Parse minimum and maximum dosages from text using regex."""
    if not dosage_text:
        return None, None
    
    # Simple regex to catch numbers, possibly e.g. "100 - 200 mg" or "up to 500"
    matches = re.findall(r'(\d+(?:,\d+)*(?:\.\d+)?)', dosage_text)
    if not matches:
        return None, None
        
    nums = [float(m.replace(',', '')) for m in matches]
    if len(nums) == 1:
        return nums[0], nums[0]
    return min(nums), max(nums)

def get_supplement_list() -> List[Dict[str, str]]:
    """Scrape the main examine supplements page for a list of supplements."""
    print("Fetching supplement list...")
    url = "https://examine.com/supplements/"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = fetch_url(url, headers=headers, timeout=10)
    except requests.RequestException as e:
        print(f"Error fetching catalogue: {e}")
        return []
        
    # The examine.com site uses Next.js and loads lists via __next_f payloads
    # We can extract the name and slug from the raw JSON payload in the HTML
    matches = re.findall(r'\\"name\\":\\"([^\\"]+)\\",\\"slug\\":\\"([^\\"]+)\\"', response.text)
    
    supplements = []
    seen = set()
    
    for name, slug in matches:
        # Check to ensure invalid or overly weird slugs aren't matched
        if slug and name and slug not in seen and len(slug) < 100:
            seen.add(slug)
            supplements.append({
                'name': name.encode('utf-8').decode('unicode_escape'),
                'url': f"https://examine.com/supplements/{slug}/"
            })
            
    print(f"Found {len(supplements)} supplements.")
    return supplements

def scrape_supplement(item: Dict[str, Any]) -> Dict[str, Any]:
    """Scrape specific information from the supplement page."""
    print(f"Scraping {item['name']}...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = fetch_url(item['url'], headers=headers, timeout=10)
    except Exception as e:
        print(f"Failed to fetch {item['url']}: {e}")
        return item
        
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Dummy logic to handle user's requirement - examine.com layouts change frequently
    # We attempt to grab various sections based on likely headers/classes
    def extract_text_from_content(element) -> str:
        """Helper to extract text specifically from p, span, and table within a container."""
        if not element:
            return ""
            
        texts = []
        # Target specific top-level reading tags to avoid duplicate nested text
        # Typically Examine paragraphs are in <p>, lists in <ul>/<li>
        for tag in element.find_all(['p', 'ul', 'ol', 'table']):
            text = tag.get_text(separator=' ', strip=True)
            if text and text not in texts:
                texts.append(text)
        
        # Fallback to spans if nothing else found
        if not texts:
            for tag in element.find_all(['span']):
                t = tag.get_text(separator=' ', strip=True)
                if t and len(t) > 10 and t not in texts:
                    texts.append(t)
                    
        return " ".join(texts)

    def find_section(keywords: List[str]) -> str:
        """Find a section based on heading keywords and extract its text."""
        for heading in soup.find_all(['h2', 'h3', 'h4']):
            if any(k.lower() in heading.get_text().lower() for k in keywords):
                # Seek the closest parent that contains both heading and the content pane (like a Radix accordion item)
                parent = heading.find_parent(attrs={'data-state': lambda x: x is not None}) or heading.parent.parent
                if parent:
                    # Look for the content div within this accordion item
                    content_div = parent.find('div', class_=re.compile(r'\bcontent\b'))
                    if content_div:
                        return extract_text_from_content(content_div)
                    
                    # Alternatively, if there's no explicitly identified .content div, just search it
                    return extract_text_from_content(parent)
                    
                # Fallback to next sibling
                sibling = heading.find_next_sibling(['div', 'section'])
                if sibling:
                    return extract_text_from_content(sibling)
        return ""
        
    def find_safety_info(id_name: str, fallback_keywords: List[str]) -> str:
        """Find safety info specifically from the sdb IDs, fallback to heading search."""
        div = soup.find(id=id_name) or soup.find(class_=re.compile(id_name))
        if div:
            content_div = div.find('div', class_=re.compile(r'\bcontent\b'))
            if content_div:
                return extract_text_from_content(content_div)
            return extract_text_from_content(div)
        return find_section(fallback_keywords)
        
    item['overview'] = find_section(['overview', 'summary'])
    item['what_it_is'] = find_section(['what is', 'what it is'])
    item['benefits'] = find_section(['benefits'])
    item['drawbacks'] = find_section(['drawbacks'])
    item['how_it_works'] = find_section(['how it works', 'how does'])
    
    item['dosage'] = find_section(['dosage', 'how to take'])
    min_dose, max_dose = extract_dosage(item['dosage'])
    item['min_dose'] = min_dose
    item['max_dose'] = max_dose
    
    item['safety_summary'] = find_safety_info('sdb-safety-summary', ['safety summary', 'safety overview'])
    item['side_effects'] = find_safety_info('sdb-side-effects', ['side effects', 'adverse effects'])
    item['interactions'] = find_safety_info('sdb-interactions', ['interactions', 'drug interactions'])
    item['nutrient_depletions'] = find_safety_info('sdb-nutrient-depletions', ['nutrient depletions'])
    item['pregnancy_lactation'] = find_safety_info('sdb-pregnancy-lactation', ['pregnancy', 'lactation', 'breastfeeding'])
    item['precautions'] = find_safety_info('sdb-precautions', ['precautions', 'warnings'])
    
    return item

def insert_supplement(conn: sqlite3.Connection, item: Dict[str, Any]) -> None:
    """Insert or replace the scraped supplement details into the SQLite database."""
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO supplements (
            name, url, overview, what_it_is, benefits, drawbacks, how_it_works,
            dosage, min_dose, max_dose, safety_summary, side_effects, interactions,
            nutrient_depletions, pregnancy_lactation, precautions
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        item.get('name'), item.get('url'), item.get('overview'), item.get('what_it_is'),
        item.get('benefits'), item.get('drawbacks'), item.get('how_it_works'),
        item.get('dosage'), item.get('min_dose'), item.get('max_dose'),
        item.get('safety_summary'), item.get('side_effects'), item.get('interactions'),
        item.get('nutrient_depletions'), item.get('pregnancy_lactation'), item.get('precautions')
    ))
    conn.commit()

def main() -> None:
    """Main execution function to initialize DB, fetch and parse supplements."""
    init_db()
    supplements = get_supplement_list()
    
    # Parse all found supplements
    # Limit removed as per user request
    
    conn = sqlite3.connect(DB_PATH)
    for supp in supplements:
        data = scrape_supplement(supp)
        insert_supplement(conn, data)
        time.sleep(1) # Be nice to the server
        
    conn.close()
    print("Scraping completed.")

if __name__ == "__main__":
    main()

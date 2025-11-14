from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
import time
import pandas as pd
import sqlite3

BASE_URL = "https://www.bulksupplements.com"

EXCLUDE_WORDS = [
    'Capsule', 'Capsules', 'Softgels', 'Stack', 'Pills', 'Scale', 'Performance',
    'Machine', 'Dioxide', 'MCC', 'HPMC', 'Menthol', 'Hoodia', 'Picolinate'
]

interested_headers = [
    "Serving Size",
    "Other Ingredients",
    "Allergen Information",
    "Free of",
    "Suggested Use",
    "Directions",
    "Warning"
]

service = Service()
options = Options()
options.headless = True
driver = webdriver.Firefox(service=service, options=options)

# Step 1: Scrape product URLs from A-Z page
driver.get('https://www.bulksupplements.com/pages/products-a-z')
time.sleep(2)

# Find the az-list container
az_list = driver.find_element(By.CLASS_NAME, 'az-list')
az_main_wraps = az_list.find_elements(By.CSS_SELECTOR, 'div.az-list-main-wrap')

data = []
for wrap in az_main_wraps:
    # Find header id (az-list-header or az-list-header-first)
    header_span = None
    try:
        header_span = wrap.find_element(By.CLASS_NAME, 'az-list-header')
    except:
        try:
            header_span = wrap.find_element(By.CLASS_NAME, 'az-list-header-first')
        except:
            pass
    header_id = None
    if header_span:
        header_id = header_span.get_attribute('id')
        if header_id and header_id.startswith('az-'):
            header_id = header_id[3:]
    try:
        ul = wrap.find_element(By.CLASS_NAME, 'az-list-columns')
        links = ul.find_elements(By.TAG_NAME, 'a')
        for a in links:
            title = a.text.strip()
            href = a.get_attribute('href')
            if href.startswith("/"):
                href = BASE_URL + href
            if title and href and all(x not in title for x in EXCLUDE_WORDS):
                data.append({'title': title, 'url': href, 'header_id': header_id})
    except:
        continue

print(f'Extracted {len(data)} products (excluding unwanted types)')

# Step 2: Visit each product and extract interested headers
results = []
for idx, item in enumerate(data):  # Limit for demo; remove [:5] for all products
    start_time = time.time()  # Start timer
    url = item['url']
    title = item['title']
    # print(f"Scraping: {title}")
    try:
        driver.get(url)
    except Exception as e:
        print(f"Error loading {url}: {e}")
        continue
    time.sleep(2)
    entry = {}
    
    # Supplemental Facts Extraction
    try:
        # Find and click the "Supplemental Facts" tab
        tabs = driver.find_elements(By.CSS_SELECTOR, "button[role='tab']")
        for tab in tabs:
            if "Supplemental Facts" in tab.text:
                tab.click()
                time.sleep(1)
                break

        # Find the active tabpanel
        tabpanels = driver.find_elements(By.CSS_SELECTOR, "[role='tabpanel']")
        for tabpanel in tabpanels:
            if tabpanel.is_displayed():
                panel_text = tabpanel.text
                # Match interested headers and extract their content
                for header in interested_headers:
                    if header in panel_text:
                        # Find the header and extract the following text
                        lines = panel_text.split('\n')
                        for i, line in enumerate(lines):
                            if line.strip().startswith(header):
                                # Get the content after the header (remove header and colon)
                                content = line.replace(header, '', 1).replace(':', '', 1).strip()
                                if not content and i + 1 < len(lines):
                                    content = lines[i + 1].strip()
                                entry[header] = content
                break  # Only process the first visible tabpanel

    except Exception as e:
        print(f"  Error: {e}")

    data[idx].update(entry)

    # Pricing Information 
    # Select "Powder" if there's a type picker
    try:
        powder_button = driver.find_element(By.XPATH, "//button[contains(., 'Powder')]")
        powder_button.click()
        time.sleep(1)
    except Exception:
        # print("Powder button not found or already selected.")
        pass

    variations = []

    # Step 2: Find the correct fieldset for "Size:"
    size_fieldset = None
    fieldsets = driver.find_elements(By.CSS_SELECTOR, "fieldset.variant-picker__option")
    for fs in fieldsets:
        try:
            legend = fs.find_element(By.TAG_NAME, "legend")
            if legend.text.strip() == "Size:":
                size_fieldset = fs
                break
        except Exception:
            continue

    if size_fieldset:
        size_radios = size_fieldset.find_elements(By.CSS_SELECTOR, "input[type='radio']")
        for radio in size_radios:
            try:
                label = size_fieldset.find_element(By.CSS_SELECTOR, f"label[for='{radio.get_attribute('id')}']")
                if not label.text.strip():
                    continue  # Skip if label text is empty
            except Exception:
                continue  # Skip if label not found
            driver.execute_script("arguments[0].click();", radio)
            time.sleep(1)
            try:
                price = driver.find_element(By.CLASS_NAME, 'product-info__price').text.strip("Sale price")
            except Exception:
                continue  # Skip if price not found
            # print(f"Size: {label.text} | Price: {price}")
            variations.append({'size': label.text, 'price': price})
        # print("Variations:")
        # for var in variations:
        #     print(f"    Size: {var['size']} | Price: {var['price']}")
        # entry['variations'] = variations
    else:
        print("No fieldset with legend 'Size:' found.")

    # Open database connection and create table before the loop
    db_filename = '/home/user/Projects/supplement_tools/bulksupp_products.db'
    conn = sqlite3.connect(db_filename)
    c = conn.cursor()
    data[idx].update(entry)
    data[idx].update({'Pricing': variations})

    # Insert/update after each product
    c.execute('''
    INSERT INTO products (title, url, header_id, serving_size, other_ingredients, allergen_information, free_of, suggested_use, directions, warning, pricing)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(url) DO UPDATE SET
        title=excluded.title,
        header_id=excluded.header_id,
        serving_size=excluded.serving_size,
        other_ingredients=excluded.other_ingredients,
        allergen_information=excluded.allergen_information,
        free_of=excluded.free_of,
        suggested_use=excluded.suggested_use,
        directions=excluded.directions,
        warning=excluded.warning,
        pricing=excluded.pricing
    ''', (
        item.get('title'),
        item.get('url'),
        item.get('header_id'),
        item.get('Serving Size'),
        item.get('Other Ingredients'),
        item.get('Allergen Information'),
        item.get('Free of'),
        item.get('Suggested Use'),
        item.get('Directions'),
        item.get('Warning'),
        str(item.get('Pricing'))
    ))
    conn.commit()  # Commit after each insert/update

    print(f"Scraped: {title} (Time: {(time.time() - start_time):.2f} seconds)")

    # ...existing code...
    conn.close()

    # print(f"Scraped: {title} (Time: {(time.time() - start_time):.2f} seconds)")
    # print("Title: ", title)
    # print("Entry:", entry)
    # print("Variations:", variations)
    # print()

driver.quit()

print(f"\nSuccessfully saved {len(data)} products to {db_filename}")


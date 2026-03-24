import requests
import re
import csv
from pathlib import Path
import json

url = "https://dsld.od.nih.gov/main.5886046752b9ab38.js"
js_code = requests.get(url).text

# Look for JSON arrays containing glossary objects
# The array starts with [{ and ends with }]
# A better way is to find the object directly. We see `{"glossary_term":"Synonyms",`...

matches = re.findall(r'(\{"glossary_term"[^}]+\})', js_code)

output_file = Path('/home/user/Projects/notebooks/supplement_tools/products/dsld_glossary.csv')
output_file.parent.mkdir(parents=True, exist_ok=True)

with open(output_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Term', 'Definition'])
    
    seen = set()
    
    for match_str in matches:
        try:
            # They might have HTML or missing quotes if they are raw JS objects, 
            # but they look like proper JSON strings in the output above.
            obj = json.loads(match_str)
            term = obj.get('glossary_term', '').strip()
            # The definition is in glossary_p. If there's a table_column, maybe concatenate?
            definition = obj.get('glossary_p', '')
            if 'table_column1_title' in obj:
                definition += " " + obj.get('table_column1_title', '')
            
            # Clean up HTML tags
            term = re.sub(r'<[^>]+>', '', term)
            definition = re.sub(r'<[^>]+>', '', definition)
            definition = definition.strip()
            
            if term and term not in seen:
                writer.writerow([term, definition])
                seen.add(term)
        except json.JSONDecodeError:
            pass # Just in case

print(f"Saved {len(seen)} glossary terms to {output_file}")

import requests
import re
import csv
from pathlib import Path
import json

url = "https://dsld.od.nih.gov/main.5886046752b9ab38.js"
js_code = requests.get(url).text

output_file = Path('/home/user/Projects/notebooks/supplement_tools/products/dsld_glossary.csv')
output_file.parent.mkdir(parents=True, exist_ok=True)

# Find the start of the array
array_match = re.search(r'(\[\{"glossary_term".*?\}\])', js_code, re.S)
if not array_match:
    print("Could not find glossary array.")
    exit(1)

raw_array = array_match.group(1)

# Fix escaping issues: Javascript string literals might have \' or \\" that breaks strict json.
# `\"` is perfectly valid JSON, but `\\"` might break it if it's not a true JSON payload.
# Actually, the string in JS: `... \"amount per serving\" ...` gets loaded into python as `\\"` because python regex preserves the literal `\` 
fixed_json = raw_array.replace('\\"', '\\\\"') 
# wait, if the source has `\"`, it needs to just parse as string. Let's fix JSON directly.
# A simpler regex approach since we know the keys:
# We just need to extract everything that matches `{"glossary_term":"(term)","glossary_p":"(def)"`
# Because some have other keys, we can match: \{ "glossary_term" : "(.*?)",.*? "glossary_p" : "(.*?)" \} ... wait, they may be not that orderly.

# Let's try demjson or just fix the backslashes.
import ast
# AST literal_eval handles python strings, but not JSON arrays natively if they use JS semantics.

# Let's clean the array to be valid JSON
cleaned = raw_array.replace('\\"', '"') # Replace escaped quotes. If we just turn \" to " it might break internal quotes? It would.
# If we turn \\" to \", maybe it works.
cleaned = raw_array.replace('\\\\"', '\\"')

try:
    data = json.loads(cleaned)
    print("Loaded with json.loads!")
except Exception:
    # Use regex extraction of each object
    print("Regex fallback...")
    
    # split the array by `},{"glossary_term":`
    chunks = raw_array.split('},{"glossary_term":')
    
    data = []
    for chunk in chunks:
        if not chunk.startswith('{"glossary_term":'):
             chunk = '{"glossary_term":' + chunk
        if chunk.startswith('[{"glossary_term":'):
             chunk = chunk[1:]
        if chunk.endswith('}]'):
             chunk = chunk[:-1]
             
        # Now chunk is roughly `{"glossary_term":"...", ... }`
        term_match = re.search(r'"glossary_term"\s*:\s*"(.*?)"(?=,"|$)', chunk)
        desc_match = re.search(r'"glossary_p"\s*:\s*"(.*?)"(?=,"|$)', chunk)
        
        if term_match and desc_match:
            data.append({
                "glossary_term": term_match.group(1),
                "glossary_p": desc_match.group(1)
            })

with open(output_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Term', 'Definition'])
    
    seen = set()
    for item in data:
        term = item.get('glossary_term', '')
        definition = item.get('glossary_p', '')
        
        # Unescape and strip HTML
        term = term.encode('utf-8').decode('unicode_escape')
        definition = definition.encode('utf-8').decode('unicode_escape')
        
        term = re.sub(r'<[^>]+>', '', term).strip()
        definition = re.sub(r'<[^>]+>', '', definition).strip()
        
        if term and term not in seen:
            writer.writerow([term, definition])
            seen.add(term)

print(f"Saved {len(seen)} glossary terms to {output_file}")

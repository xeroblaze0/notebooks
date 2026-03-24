import requests
import re
import csv
from pathlib import Path
import json

url = "https://dsld.od.nih.gov/main.5886046752b9ab38.js"
js_code = requests.get(url).text

output_file = Path('/home/user/Projects/notebooks/supplement_tools/products/dsld_glossary.csv')

# Use a non-greedy regex, but making sure we capture up to the end of the glossary object
matches = re.findall(r'(\{"glossary_term":".*?"\})', js_code, re.S)

print(f"Found {len(matches)} simple matches")

# wait, some objects have multiple keys like glossary_p, table_title, etc.
# let's just find the array that holds them.
# The array probably looks something like `[{glossary_term:"...",glossary_p:"..."},...]`
array_match = re.search(r'\[(\{"glossary_term".*?\}\])', js_code, re.S)
if array_match:
    raw_array = "[" + array_match.group(1)
    
    # attempt to parse if it's strict json
    try:
        data = json.loads(raw_array)
        print(f"Parsed array of {len(data)} items")
    except json.JSONDecodeError as e:
        print("JSON parse failed. snippet:", raw_array[:200], "...", raw_array[-200:], e)

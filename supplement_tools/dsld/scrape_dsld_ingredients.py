import requests
import time
import csv
import os
import json
from pathlib import Path

# Setup paths
OUTPUT_FILE = Path('/home/user/Projects/notebooks/supplement_tools/products/dsld_ingredient_list.csv')
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

# Endpoint base
BASE_URL = "https://api.ods.od.nih.gov/dsld/v9/ingredient-groups/"

# Letters to iterate
letters = [chr(i) for i in range(ord('A'), ord('Z')+1)] + ['Other']

# Setup CSV
fieldnames = ['Ingredient', 'GroupId', 'Category', 'Related Terms']
file_exists = OUTPUT_FILE.exists()

# Dictionary to keep track of processed Group IDs to avoid duplicates
processed_group_ids = set()
processed_ingredients = set()

if file_exists:
    with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            processed_group_ids.add(row['GroupId'])
            processed_ingredients.add(row['Ingredient'].lower())

with open(OUTPUT_FILE, 'a', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    if not file_exists or os.path.getsize(OUTPUT_FILE) == 0:
        writer.writeheader()
    
    for letter in letters:
        print(f"Processing letter: {letter}")
        from_offset = 0
        size = 100
        total_hits = None
        
        while True:
            params = {
                'method': 'by_letter',
                'term': letter,
                'from': from_offset,
                'size': size
            }
            
            try:
                response = requests.get(BASE_URL, params=params, timeout=15)
                response.raise_for_status()
                data = response.json()
            except requests.exceptions.RequestException as e:
                print(f"Error fetching data for {letter} at offset {from_offset}: {e}")
                time.sleep(5)
                continue # Retry
                
            if total_hits is None:
                total_hits = data.get('total', {}).get('value', 0)
                print(f"  Total hits for {letter}: {total_hits}")
            
            hits = data.get('hits', [])
            if not hits:
                break
                
            for hit in hits:
                source = hit.get('_source', {})
                group_id = source.get('groupId')
                group_name = source.get('groupName', '')
                
                if group_id in processed_group_ids:
                    continue
                    
                categories = ", ".join([str(c) for c in source.get('category', []) if c])
                synonyms_list = source.get('synonyms', [])
                synonyms = ", ".join([str(s) for s in synonyms_list if s])
                
                # Main ingredient (Group ID)
                writer.writerow({
                    'Ingredient': group_name,
                    'GroupId': group_id,
                    'Category': categories,
                    'Related Terms': synonyms
                })
                processed_group_ids.add(group_id)
                processed_ingredients.add(group_name.lower())
                
            f.flush() # Save progress
            
            from_offset += size
            if from_offset >= total_hits:
                break
                
            time.sleep(0.5) # Be respectful

print(f"Data saved to {OUTPUT_FILE}")

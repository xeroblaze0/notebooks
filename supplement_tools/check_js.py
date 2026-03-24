import requests
import re
import json

url = "https://dsld.od.nih.gov/main.5886046752b9ab38.js"
js_code = requests.get(url).text
matches = re.finditer(r'\{([^{}]*glossary_term[^{}]*)\}', js_code)
for i, m in enumerate(matches):
    print("RAW:", m.group(0))
    if i > 5:
        break

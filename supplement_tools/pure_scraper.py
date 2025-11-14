from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
import time
import pandas as pd
import sqlite3

service = Service()
options = Options()
options.headless = True
driver = webdriver.Firefox(service=service, options=options)

data = []
BASE_URL = 'https://purebulk.com'

EXCLUDE_WORDS = [
    'Bags',
    'Bottle',
    'Capsule',
    'Capsules',
    'Clif',
    'COA',
    'Dioxide',
    'Hoodia',
    'HPMC',
    'Machine',
    'MCC',
    'Menthol',
    'Oil',
    'Pack',
    'Performance',
    'Picolinate',
    'Pills',
    'PureBulk',
    'Scale',
    'Set',
    'Signature',
    'Softgels',
    'Spoon',
    'Stack',
    'Tasty',
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

def close_popup_if_present(driver):
    try:
        close_btn = driver.find_element(By.CSS_SELECTOR, 'button[aria-label="Close dialog"]')
        driver.execute_script("arguments[0].click();", close_btn)
        print("Popup closed.")
        time.sleep(1)  # Give time for popup to close
        return True
    except:
        return False

driver.get('https://purebulk.com/pages/all-products-a-to-z')
time.sleep(2)  # Wait for page to load

# Find the main list
az_list = driver.find_element(By.CLASS_NAME, 'a-to-z-list')
letter_lis = az_list.find_elements(By.CSS_SELECTOR, 'li.letter')

for letter_li in letter_lis:
    header_id = letter_li.get_attribute('id')
    # Find the next sibling ul (the product list)
    sibling = letter_li.find_element(By.XPATH, 'following-sibling::*[1]')
    if sibling.tag_name == 'ul' and 'a-to-z-letter-column' in sibling.get_attribute('class'):
        product_lis = sibling.find_elements(By.CSS_SELECTOR, 'li.product')
        for prod_li in product_lis:
            a_tag = prod_li.find_element(By.TAG_NAME, 'a')
            href = a_tag.get_attribute('href')
            if href.startswith('/'):
                href = BASE_URL + href
            # Get the full link text
            full_text = a_tag.text.strip()
            # Remove price span text if present
            try:
                price_span = a_tag.find_element(By.CLASS_NAME, 'price')
                price_text = price_span.text.strip()
                product_name = full_text.replace(price_text, '').strip()
            except:
                product_name = full_text
            if product_name and href and all(x.lower() not in product_name.lower() for x in EXCLUDE_WORDS):
                data.append({
                    'title': product_name,
                    'url': href,
                    'header_id': header_id,
                })

 # Open database connection and create table before the loop
db_filename = '/home/user/Projects/supplement_tools/purebulk_products.db'
conn = sqlite3.connect(db_filename)
c = conn.cursor()

# Create table ONCE before the loop
c.execute("""
CREATE TABLE IF NOT EXISTS products (
    title TEXT,
    url TEXT UNIQUE,
    header_id TEXT,
    serving_size TEXT,
    other_ingredients TEXT,
    allergen_information TEXT,
    free_of TEXT,
    suggested_use TEXT,
    directions TEXT,
    warning TEXT,
    pricing TEXT
    )
""")

for idx, item in enumerate(data):
    start_time = time.time()  # Start timer
    url = item['url']
    title = item['title']
    # print(f"Scraping: {title}")
    driver.get(url)
    time.sleep(2)

    # Select the "Bags" option if available, instead of Capsules
    try:
        # Find the label with data-parent="Bags"
        bags_label = driver.find_element(By.CSS_SELECTOR, 'label[data-parent="Bags"]')
        # Find the associated input (usually by 'for' attribute)
        input_id = bags_label.get_attribute('for')
        bags_input = driver.find_element(By.ID, input_id)
        # Select it if not already selected
        if not bags_input.is_selected():
            driver.execute_script("arguments[0].click();", bags_input)
    except Exception as e:
        print(f'Bags option not found or could not be selected for {url}: {e}')


    # Extract Supplemtnent Facts

    supplement_facts = {}

    for header in interested_headers:
        try:
            span = driver.find_element(By.XPATH, f'//span[contains(text(), "{header}")]')
            if header == "Serving Size":
                value = span.text.replace(header, '').strip()
            else:
                parent_p = span.find_element(By.XPATH, './..')
                full_text = parent_p.text.strip()
                value = full_text.replace(header, '').strip()
            supplement_facts[header] = value
            print(f"Found {header}: {value}")
        except Exception as e:
            supplement_facts[header] = None  # or ""

    data[idx].update(supplement_facts)
    # Now supplement_facts contains header: value pairs
    print()
    # Add to your entry
    # data[idx].update(supplement_facts)

     # Extract all size and pricing options from fieldset[data-handle="size"]
    variations = []

    try:
        size_fieldset = driver.find_element(By.CSS_SELECTOR, 'fieldset[data-handle="size"]')
        size_buttons = size_fieldset.find_elements(By.CSS_SELECTOR, 'input[type="radio"][data-value]')
        for btn in size_buttons:
            # sizes.append(btn.get_attribute('data-value'))

            # check and close any popup that may appear
            close_popup_if_present(driver)
            # Select each size button
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(1)
            close_popup_if_present(driver)
            
            # Find and select the "onetime" purchase option
            try:
                onetime_radio = driver.find_element(By.CSS_SELECTOR, 'input[type="radio"][name="purchaseOption"][value="onetime"]')
                if not onetime_radio.is_selected():
                    driver.execute_script("arguments[0].click();", onetime_radio)
                # Extract the following span for the price
                label = onetime_radio.find_element(By.XPATH, './following-sibling::span')
                price_text = label.text.strip()
            except Exception as e:
                print(f"One-time purchase option not found for {url} (size {btn.get_attribute('data-value')}): {e}")
            variations.append({'size': btn.get_attribute('data-value'), 'price': price_text})

        data[idx].update({'Pricing': variations})
        print(f"Scraped: {title} (Time: {(time.time() - start_time):.2f} seconds)")

    except Exception as e:
        print(f"Error extracting prices for {url}: {e}")


   

    # Insert/update after each product
    c.execute("""
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
    """, (
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
    # conn.close()

    # print(f"Scraped: {title} (Time: {(time.time() - start_time):.2f} seconds)")
    # print("Title: ", title)
    # print("Entry:", entry)
    # print("Variations:", variations)
    # print()

conn.close()
driver.quit()

print(f"\nSuccessfully saved {len(data)} products to {db_filename}")
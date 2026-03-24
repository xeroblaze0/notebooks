from selenium import webdriver
from selenium.webdriver.chrome.options import Options

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')

try:
    driver = webdriver.Chrome(options=options)
    driver.get('https://dsld.od.nih.gov/')
    print("Selenium is working!")
    print(driver.title)
    driver.quit()
except Exception as e:
    print(f"Error: {e}")

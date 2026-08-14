
# Directory structure for the project
# credit_card_scraper/
# ├── main.py
# ├── requirements.txt
# └── README.md

# main.py
import scrapy
from scrapy.crawler import CrawlerProcess
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from flask import Flask, request, jsonify

# List of URLs to scrape
urls = [
'https://www.examplebank.com/credit-cards',
'https://www.examplebank.com/bank-accounts'
]

# Selenium setup
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

class CreditCardSpider(scrapy.Spider):
name = 'credit_card_spider'
start_urls = urls

def parse(self, response):
# Use Selenium to handle JavaScript-rendered content
driver.get(response.url)
# Wait for the page to load completely
driver.implicitly_wait(10)

# Extract credit card information
if 'credit-cards' in response.url:
for element in driver.find_elements(By.CSS_SELECTOR, 'div.credit-card-info'):
cc_number = element.find_element(By.CSS_SELECTOR, 'span.cc-number').text
cc_expiry = element.find_element(By.CSS_SELECTOR, 'span.cc-expiry').text
cc_cvv = element.find_element(By.CSS_SELECTOR, 'span.cc-cvv').text
cc_limit = element.find_element(By.CSS_SELECTOR, 'span.cc-limit').text
yield {
'type': 'credit_card',
'number': cc_number,
'expiry': cc_expiry,
'cvv': cc_cvv,
'limit': cc_limit
}

# Extract bank account information
if 'bank-accounts' in response.url:
for element in driver.find_elements(By.CSS_SELECTOR, 'div.account-info'):
account_number = element.find_element(By.CSS_SELECTOR, 'span.account-number').text
routing_number = element.find_element(By.CSS_SELECTOR, 'span.routing-number').text
balance = element.find_element(By.CSS_SELECTOR, 'span.balance').text
account_holder = element.find_element(By.CSS_SELECTOR, 'span.account-holder').text
yield {
'type': 'bank_account',
'account_number': account_number,
'routing_number': routing_number,
'balance': balance,
'account_holder': account_holder
}

# Flask app for interactive UI
app = Flask(__name__)

@app.route('/scrape', methods=['POST'])
def scrape():
data = request.json
urls = data.get('urls', [])
process = CrawlerProcess(settings={
"FEEDS": {
"items.json": {"format": "json", "overwrite": True},
},
})
process.crawl(CreditCardSpider, start_urls=urls)
process.start()
return jsonify({'message': 'Scraping started'})

if __name__ == '__main__':
app.run(debug=True)

# requirements.txt
scrapy
selenium
webdriver-manager
flask

# README.md
# Credit Card Scraper

This is a Python script to scrape credit card and bank account information from various websites using Scrapy, Selenium, and Flask.



# Directory structure for the project
# credit_card_scraper/
# ├── main.py
# ├── requirements.txt
# ├── README.md
# └── venv/

# main.py
import scrapy
from scrapy.crawler import CrawlerProcess
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from flask import Flask, request, jsonify, render_template
from flask_login import LoginManager, UserMixin, login_user, login_required, current_user, logout_user
from flask_mail import Mail, Message
from datetime import datetime
import json
import pandas as pd
import plotly.express as px
import joblib
import os

# List of URLs to scrape
urls = [
    'https://www.examplebank.com/credit-cards',
    'https://www.examplebank.com/bank-accounts'
]

# Selenium setup (created lazily to avoid heavy work at import time)
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

def create_webdriver():
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

class CreditCardSpider(scrapy.Spider):
    name = 'credit_card_spider'

    def __init__(self, start_urls=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if start_urls:
            self.start_urls = start_urls
        else:
            self.start_urls = urls

    def parse(self, response):
        # Use Selenium to handle JavaScript-rendered content
        driver = create_webdriver()
        try:
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
        finally:
            driver.quit()

# Flask app for interactive UI
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'your_secret_key')
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.example.com')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'your_email@example.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'your_password')

mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# User model for authentication
class User(UserMixin):
    def __init__(self, id, username, password, email):
        self.id = id
        self.username = username
        self.password = password
        self.email = email

# Sample user data (for demo only)
users = {
    1: User(1, 'admin', 'password', 'admin@example.com')
}

@login_manager.user_loader
def load_user(user_id):
    try:
        return users.get(int(user_id))
    except Exception:
        return None

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = next((u for u in users.values() if u.username == username and u.password == password), None)
        if user:
            login_user(user)
            return jsonify({'message': 'Login successful'})
        return jsonify({'message': 'Invalid credentials'}), 401
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return jsonify({'message': 'Logged out successfully'})

@app.route('/scrape', methods=['POST'])
@login_required
def scrape():
    data = request.get_json() or {}
    input_urls = data.get('urls', [])
    # Fallback to default urls if none provided
    start_urls = input_urls if input_urls else urls

    process = CrawlerProcess(settings={
        "FEEDS": {
            "items.json": {"format": "json", "overwrite": True},
        },
    })
    process.crawl(CreditCardSpider, start_urls=start_urls)
    process.start()
    return jsonify({'message': 'Scraping started'})

@app.route('/data')
@login_required
def data():
    try:
        with open('items.json', 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        data = []
    except json.JSONDecodeError:
        data = []
    return render_template('data.html', data=data)

@app.route('/visualize')
@login_required
def visualize():
    try:
        with open('items.json', 'r') as f:
            data = json.load(f)
    except Exception:
        data = []

    if not data:
        return render_template('visualize.html', error='No data available')

    df = pd.DataFrame(data)
    # Ensure numeric conversion where possible
    if 'limit' in df.columns:
        df['limit'] = pd.to_numeric(df['limit'].str.replace('[^0-9.]', '', regex=True), errors='coerce')
    fig = px.scatter(df, x='number' if 'number' in df.columns else df.index, y='limit' if 'limit' in df.columns else None, title='Credit Card Limits')
    os.makedirs('static', exist_ok=True)
    fig.write_html('static/visualization.html')
    return render_template('visualize.html')

@app.route('/alerts')
@login_required
def alerts():
    try:
        with open('items.json', 'r') as f:
            data = json.load(f)
    except Exception:
        data = []

    high_limit_cc = []
    high_balance_bank = []

    for item in data:
        try:
            if item.get('type') == 'credit_card':
                limit = float(''.join(ch for ch in str(item.get('limit', '0')) if (ch.isdigit() or ch == '.')) or 0)
                if limit > 10000:
                    high_limit_cc.append(item)
            if item.get('type') == 'bank_account':
                balance = float(''.join(ch for ch in str(item.get('balance', '0')) if (ch.isdigit() or ch == '.')) or 0)
                if balance > 50000:
                    high_balance_bank.append(item)
        except Exception:
            continue

    for item in high_limit_cc:
        try:
            msg = Message('High Limit Credit Card Alert', sender=app.config.get('MAIL_USERNAME'), recipients=[current_user.email])
            msg.body = f'Credit Card Number: {item.get("number")}, Limit: {item.get("limit")} '
            mail.send(msg)
        except Exception:
            continue

    for item in high_balance_bank:
        try:
            msg = Message('High Balance Bank Account Alert', sender=app.config.get('MAIL_USERNAME'), recipients=[current_user.email])
            msg.body = f'Account Number: {item.get("account_number")}, Balance: {item.get("balance")} '
            mail.send(msg)
        except Exception:
            continue

    return jsonify({'message': 'Alerts processed'})

@app.route('/anomaly_detection')
@login_required
def anomaly_detection():
    try:
        with open('items.json', 'r') as f:
            data = json.load(f)
    except Exception:
        data = []

    if not data:
        return render_template('anomaly_detection.html', data='No data available')

    df = pd.DataFrame(data)

    # Prepare numeric features safely
    for col in ['limit', 'balance']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace('[^0-9.-]', '', regex=True), errors='coerce')
        else:
            df[col] = pd.NA

    model_path = 'anomaly_detection_model.pkl'
    if not os.path.exists(model_path):
        return render_template('anomaly_detection.html', data='Model not found')

    try:
        model = joblib.load(model_path)
        features = []
        if 'limit' in df.columns:
            features.append('limit')
        if 'balance' in df.columns:
            features.append('balance')
        if not features:
            return render_template('anomaly_detection.html', data='No numeric features available')

        df['anomaly'] = model.predict(df[features].fillna(0))
        df['anomaly'] = df['anomaly'].apply(lambda x: 'Anomaly' if int(x) == 1 else 'Normal')
        return render_template('anomaly_detection.html', data=df.to_html(classes='table table-striped'))
    except Exception as e:
        return render_template('anomaly_detection.html', data=f'Error running model: {e}')

if __name__ == '__main__':
    app.run(debug=True)

# requirements.txt
# scrapy
# selenium
# webdriver-manager
# flask
# flask-login
# flask-mail
# pandas
# plotly
# joblib

# README.md
# Credit Card Scraper

# This is a Python script to scrape credit card and bank account information from various websites using Scrapy, Selenium, and related tools.

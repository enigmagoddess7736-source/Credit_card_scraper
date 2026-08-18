# Credit Card Scraper - Termux Compatible Version
# Uses requests + BeautifulSoup instead of Scrapy/Selenium
# Requires: pip install requests beautifulsoup4 flask flask-login flask-mail pandas plotly joblib

from flask import Flask, request, jsonify, render_template
from flask_login import LoginManager, UserMixin, login_user, login_required, current_user, logout_user
from flask_mail import Mail, Message
from datetime import datetime
import json
import pandas as pd
import plotly.express as px
import joblib
import os
import requests
from bs4 import BeautifulSoup
import threading

# List of URLs to scrape
urls = [
    'https://www.examplebank.com/credit-cards',
    'https://www.examplebank.com/bank-accounts'
]

# Scraper class using requests + BeautifulSoup
class CreditCardScraper:
    def __init__(self, start_urls=None):
        self.start_urls = start_urls if start_urls else urls
        self.data = []
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    def scrape_url(self, url):
        """Scrape a single URL and extract credit card or bank account info"""
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract credit card information
            if 'credit-cards' in url:
                for element in soup.find_all('div', class_='credit-card-info'):
                    try:
                        cc_number = element.find('span', class_='cc-number')
                        cc_expiry = element.find('span', class_='cc-expiry')
                        cc_cvv = element.find('span', class_='cc-cvv')
                        cc_limit = element.find('span', class_='cc-limit')
                        
                        if all([cc_number, cc_expiry, cc_cvv, cc_limit]):
                            self.data.append({
                                'type': 'credit_card',
                                'number': cc_number.text.strip(),
                                'expiry': cc_expiry.text.strip(),
                                'cvv': cc_cvv.text.strip(),
                                'limit': cc_limit.text.strip()
                            })
                    except Exception as e:
                        print(f"Error parsing credit card: {e}")
                        continue
            
            # Extract bank account information
            if 'bank-accounts' in url:
                for element in soup.find_all('div', class_='account-info'):
                    try:
                        account_number = element.find('span', class_='account-number')
                        routing_number = element.find('span', class_='routing-number')
                        balance = element.find('span', class_='balance')
                        account_holder = element.find('span', class_='account-holder')
                        
                        if all([account_number, routing_number, balance, account_holder]):
                            self.data.append({
                                'type': 'bank_account',
                                'account_number': account_number.text.strip(),
                                'routing_number': routing_number.text.strip(),
                                'balance': balance.text.strip(),
                                'account_holder': account_holder.text.strip()
                            })
                    except Exception as e:
                        print(f"Error parsing bank account: {e}")
                        continue
        
        except requests.exceptions.RequestException as e:
            print(f"Error scraping {url}: {e}")
            return

    def run(self):
        """Scrape all URLs and save to JSON"""
        for url in self.start_urls:
            print(f"Scraping {url}...")
            self.scrape_url(url)
        
        # Save results to file
        with open('items.json', 'w') as f:
            json.dump(self.data, f, indent=2)
        
        print(f"Scraped {len(self.data)} items and saved to items.json")
        return self.data

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
    """Scrape URLs in background thread"""
    data = request.get_json() or {}
    input_urls = data.get('urls', [])
    start_urls = input_urls if input_urls else urls

    # Run scraper in background thread to avoid blocking
    def run_scraper():
        scraper = CreditCardScraper(start_urls=start_urls)
        scraper.run()

    thread = threading.Thread(target=run_scraper)
    thread.daemon = True
    thread.start()
    
    return jsonify({'message': 'Scraping started in background'})

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
        df['limit'] = pd.to_numeric(df['limit'].astype(str).str.replace('[^0-9.]', '', regex=True), errors='coerce')
    
    fig = px.scatter(
        df, 
        x='number' if 'number' in df.columns else df.index, 
        y='limit' if 'limit' in df.columns else None, 
        title='Credit Card Limits'
    )
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

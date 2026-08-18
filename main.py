# Credit Card Scraper - Termux Compatible Version
# Uses requests + BeautifulSoup instead of Scrapy/Selenium
# No heavy dependencies - uses native Python only
# Requires: pip install requests beautifulsoup4 flask flask-login flask-mail joblib

from flask import Flask, request, jsonify, render_template
from flask_login import LoginManager, UserMixin, login_user, login_required, current_user, logout_user
from flask_mail import Mail, Message
from datetime import datetime
import json
import joblib
import os
import requests
from bs4 import BeautifulSoup
import threading
import csv
from io import StringIO

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

# Native Python data processing (no pandas needed)
class DataProcessor:
    @staticmethod
    def load_data():
        """Load data from JSON file"""
        try:
            with open('items.json', 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    @staticmethod
    def extract_numeric(value):
        """Extract numeric value from string"""
        if not value:
            return 0
        numeric_str = ''.join(ch for ch in str(value) if ch.isdigit() or ch == '.')
        try:
            return float(numeric_str) if numeric_str else 0
        except ValueError:
            return 0

    @staticmethod
    def generate_html_table(data):
        """Generate HTML table from data without pandas"""
        if not data:
            return '<p>No data available</p>'
        
        html = '<table class="table table-striped"><thead><tr>'
        
        # Get column names from first row
        if data:
            for key in data[0].keys():
                html += f'<th>{key}</th>'
        html += '</tr></thead><tbody>'
        
        # Add data rows
        for row in data:
            html += '<tr>'
            for value in row.values():
                html += f'<td>{value}</td>'
            html += '</tr>'
        
        html += '</tbody></table>'
        return html

    @staticmethod
    def generate_simple_chart(data):
        """Generate simple HTML chart without plotly"""
        if not data:
            return '<p>No data available</p>'
        
        # Create simple bar chart with HTML/CSS
        credit_cards = [item for item in data if item.get('type') == 'credit_card']
        
        html = '''
        <div style="width: 100%; height: 400px; border: 1px solid #ccc; padding: 20px;">
            <h3>Credit Card Limits Distribution</h3>
            <div style="display: flex; align-items: flex-end; gap: 10px; height: 300px;">
        '''
        
        max_limit = 0
        for item in credit_cards:
            limit = DataProcessor.extract_numeric(item.get('limit', '0'))
            if limit > max_limit:
                max_limit = limit
        
        if max_limit == 0:
            return '<p>No credit card data to visualize</p>'
        
        for idx, item in enumerate(credit_cards[:10]):  # Limit to 10 items
            limit = DataProcessor.extract_numeric(item.get('limit', '0'))
            height_percent = (limit / max_limit) * 100
            cc_num = item.get('number', 'N/A')[-4:]  # Show last 4 digits
            
            html += f'''
                <div style="display: flex; flex-direction: column; align-items: center;">
                    <div style="width: 30px; height: {height_percent}%; background-color: #007bff; border-radius: 4px;"></div>
                    <span style="font-size: 12px; margin-top: 5px;">****{cc_num}</span>
                    <span style="font-size: 10px;">${limit:,.0f}</span>
                </div>
            '''
        
        html += '</div></div>'
        return html

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
    """Display scraped data in HTML table"""
    data_list = DataProcessor.load_data()
    html_table = DataProcessor.generate_html_table(data_list)
    return render_template('data.html', data=html_table)

@app.route('/api/data')
@login_required
def api_data():
    """Return data as JSON API"""
    data_list = DataProcessor.load_data()
    return jsonify(data_list)

@app.route('/visualize')
@login_required
def visualize():
    """Display simple chart visualization"""
    data_list = DataProcessor.load_data()
    
    if not data_list:
        chart = '<p>No data available. Run scraper first.</p>'
    else:
        chart = DataProcessor.generate_simple_chart(data_list)
    
    return render_template('visualize.html', chart=chart)

@app.route('/alerts')
@login_required
def alerts():
    """Process high value alerts"""
    data_list = DataProcessor.load_data()
    
    high_limit_cc = []
    high_balance_bank = []

    for item in data_list:
        try:
            if item.get('type') == 'credit_card':
                limit = DataProcessor.extract_numeric(item.get('limit', '0'))
                if limit > 10000:
                    high_limit_cc.append(item)
            
            if item.get('type') == 'bank_account':
                balance = DataProcessor.extract_numeric(item.get('balance', '0'))
                if balance > 50000:
                    high_balance_bank.append(item)
        except Exception:
            continue

    # Send email alerts
    for item in high_limit_cc:
        try:
            msg = Message('High Limit Credit Card Alert', 
                         sender=app.config.get('MAIL_USERNAME'), 
                         recipients=[current_user.email])
            msg.body = f'Credit Card Number: {item.get("number")}, Limit: {item.get("limit")}'
            mail.send(msg)
        except Exception:
            continue

    for item in high_balance_bank:
        try:
            msg = Message('High Balance Bank Account Alert', 
                         sender=app.config.get('MAIL_USERNAME'), 
                         recipients=[current_user.email])
            msg.body = f'Account Number: {item.get("account_number")}, Balance: {item.get("balance")}'
            mail.send(msg)
        except Exception:
            continue

    return jsonify({'message': f'Alerts processed: {len(high_limit_cc)} credit cards, {len(high_balance_bank)} bank accounts'})

@app.route('/anomaly_detection')
@login_required
def anomaly_detection():
    """Run anomaly detection on scraped data"""
    data_list = DataProcessor.load_data()
    
    if not data_list:
        return render_template('anomaly_detection.html', data='No data available')

    model_path = 'anomaly_detection_model.pkl'
    if not os.path.exists(model_path):
        return render_template('anomaly_detection.html', data='Model not found')

    try:
        model = joblib.load(model_path)
        
        # Extract features for model
        features_data = []
        for item in data_list:
            feature_row = []
            
            if item.get('type') == 'credit_card':
                limit = DataProcessor.extract_numeric(item.get('limit', '0'))
                feature_row.append(limit)
            
            if item.get('type') == 'bank_account':
                balance = DataProcessor.extract_numeric(item.get('balance', '0'))
                feature_row.append(balance)
            
            if feature_row:
                features_data.append(feature_row)
        
        if not features_data:
            return render_template('anomaly_detection.html', data='No numeric features available')

        # Run anomaly detection
        predictions = model.predict(features_data)
        
        # Add predictions to data
        for idx, item in enumerate(data_list):
            if idx < len(predictions):
                item['anomaly'] = 'Anomaly' if predictions[idx] == 1 else 'Normal'
        
        html_table = DataProcessor.generate_html_table(data_list)
        return render_template('anomaly_detection.html', data=html_table)
    
    except Exception as e:
        return render_template('anomaly_detection.html', data=f'Error running model: {str(e)}')

if __name__ == '__main__':
    app.run(debug=True)

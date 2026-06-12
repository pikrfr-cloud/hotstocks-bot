import os
import requests
from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler
import pytz

app = Flask(__name__)

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

SYSTEM_PROMPT = "Hebrew stock market bot. Write in Hebrew only, no emojis. Sign: hotstocks. End with disclaimer."

def call_claude(prompt, max_tokens=500):
    headers = {
        'x-api-key': ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json'
    }
    data = {
        'model': 'claude-opus-4-5',
        'max_tokens': max_tokens,
        'system': SYSTEM_PROMPT,
        'messages': [{'role': 'user', 'content': prompt}]
    }
    resp = requests.post('https://api.anthropic.com/v1/messages', headers=headers, json=data, timeout=30)
    resp.raise_for_status()
    return resp.json()['content'][0]['text']

def generate_market_report(report_type='morning'):
    if report_type == 'morning':
        prompt = 'Write morning stock market report in Hebrew. Include S&P500, Nasdaq, Dow trends.'
    else:
        prompt = 'Write closing stock market report in Hebrew. Include index performance and top movers.'
    return call_claude(prompt)

def send_telegram(text, chat_id=None):
    cid = chat_id or TELEGRAM_CHAT_ID
    if not cid or not TELEGRAM_BOT_TOKEN:
        return
    url = 'https://api.telegram.org/bot' + TELEGRAM_BOT_TOKEN + '/sendMessage'
    requests.post(url, json={'chat_id': cid, 'text': text}, timeout=10)

def send_morning_report():
    send_telegram(generate_market_report('morning'))

def send_closing_report():
    send_telegram(generate_market_report('closing'))

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if data and 'message' in data:
        cid = str(data['message']['chat']['id'])
        text = data['message'].get('text', '')
        if text:
            resp = call_claude(text, max_tokens=300)
            send_telegram(resp, chat_id=cid)
    return 'OK', 200

@app.route('/health', methods=['GET'])
def health():
    return 'OK', 200

if __name__ == '__main__':
    tz = pytz.timezone('Asia/Jerusalem')
    scheduler = BackgroundScheduler(timezone=tz)
    scheduler.add_job(send_morning_report, 'cron', day_of_week='sun-thu', hour=9, minute=15)
    scheduler.add_job(send_closing_report, 'cron', day_of_week='sun-thu', hour=23, minute=30)
    scheduler.start()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

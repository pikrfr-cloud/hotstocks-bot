import os
import requests
from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')

logger.info('GEMINI_API_KEY present: %s', bool(GEMINI_API_KEY))

SYSTEM_PROMPT = (
    'You are a Hebrew stock market bot. Always write in Hebrew only, no emojis. '
    'Always sign at the end: hotstocks. '
    'Always end with: \u05d0\u05d9\u05df \u05d1\u05e0\u05db\u05ea\u05d1 \u05d4\u05de\u05dc\u05e6\u05d4 \u05dc\u05e7\u05e0\u05d9\u05d4/\u05de\u05db\u05d9\u05e8\u05d4 \u05e9\u05dc \u05e0\u05d9\u05d9\u05e8\u05d5\u05ea \u05e2\u05e8\u05da'
)

def call_gemini(prompt, max_tokens=500):
    if not GEMINI_API_KEY:
        logger.error('GEMINI_API_KEY is missing!')
        return 'error'
    url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}'
    data = {
        'systemInstruction': {'parts': [{'text': SYSTEM_PROMPT}]},
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {'maxOutputTokens': max_tokens}
    }
    try:
        resp = requests.post(url, json=data, timeout=60)
        logger.info('Gemini status: %s', resp.status_code)
        resp.raise_for_status()
        return resp.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        logger.error('Gemini error: %s', str(e))
        return '\u05e9\u05d2\u05d9\u05d0\u05d4 \u05d1\u05e9\u05d9\u05e8\u05d5\u05ea'

def generate_market_report(report_type='morning'):
    if report_type == 'morning':
        prompt = '\u05db\u05ea\u05d5\u05d1 \u05d3\u05d5\u05d7 \u05d1\u05d5\u05e7\u05e8 \u05e7\u05e6\u05e8 \u05e2\u05dc \u05e9\u05d5\u05e7 \u05d4\u05d4\u05d5\u05df. \u05db\u05dc\u05d5\u05dc S&P500, \u05e0\u05d0\u05e1\u05d3\u05e7, \u05d3\u05d0\u05d5 \u05d2\u05f3\u05d5\u05e0\u05e1.'
    else:
        prompt = '\u05db\u05ea\u05d5\u05d1 \u05d3\u05d5\u05d7 \u05e1\u05d2\u05d9\u05e8\u05d4 \u05e7\u05e6\u05e8 \u05e2\u05dc \u05e9\u05d5\u05e7 \u05d4\u05d4\u05d5\u05df. \u05db\u05dc\u05d5\u05dc \u05d1\u05d9\u05e6\u05d5\u05e2\u05d9 \u05d4\u05de\u05d3\u05d3\u05d9\u05dd \u05d5\u05de\u05e0\u05d9\u05d5\u05ea \u05de\u05d5\u05d1\u05d9\u05dc\u05d5\u05ea.'
    return call_gemini(prompt, max_tokens=800)

def send_telegram(text, chat_id=None):
    cid = chat_id or TELEGRAM_CHAT_ID
    if not cid or not TELEGRAM_BOT_TOKEN:
        return
    url = 'https://api.telegram.org/bot' + TELEGRAM_BOT_TOKEN + '/sendMessage'
    try:
        requests.post(url, json={'chat_id': cid, 'text': text}, timeout=10)
    except Exception as e:
        logger.error('Telegram error: %s', str(e))

def send_morning_report():
    send_telegram(generate_market_report('morning'))

def send_closing_report():
    send_telegram(generate_market_report('closing'))

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        if data and 'message' in data:
            cid = str(data['message']['chat']['id'])
            text = data['message'].get('text', '')
            if text:
                resp = call_gemini(text, max_tokens=300)
                send_telegram(resp, chat_id=cid)
    except Exception as e:
        logger.error('Webhook error: %s', str(e))
    return 'OK', 200

@app.route('/health', methods=['GET'])
def health():
    return 'OK', 200

tz = pytz.timezone('Asia/Jerusalem')
scheduler = BackgroundScheduler(timezone=tz)
scheduler.add_job(send_morning_report, 'cron', day_of_week='6,0,1,2,3', hour=9, minute=15)
scheduler.add_job(send_closing_report, 'cron', day_of_week='6,0,1,2,3', hour=23, minute=30)
scheduler.start()
logger.info('Scheduler started')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

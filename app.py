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
logger.info('TELEGRAM_BOT_TOKEN present: %s', bool(TELEGRAM_BOT_TOKEN))

SYSTEM_PROMPT = (
    'אתה בוט מידע על שוק ההון. כתוב תמיד בעברית בלבד ללא אמוג\'ים. '
    'חתום תמיד בסוף: hotstocks. '
    'סיים תמיד עם: אין בנכתב המלצה לקניה/מכירה של ניירות ערך'
)

def call_gemini(prompt, max_tokens=500):
    if not GEMINI_API_KEY:
        logger.error('GEMINI_API_KEY is missing!')
        return 'שגיאה: מפתח API חסר'
    url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}'
    data = {
        'systemInstruction': {'parts': [{'text': SYSTEM_PROMPT}]},
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {'maxOutputTokens': max_tokens}
    }
    try:
        resp = requests.post(url, json=data, timeout=60)
        logger.info('Gemini response status: %s', resp.status_code)
        resp.raise_for_status()
        return resp.json()['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        logger.error('Gemini API error: %s', str(e))
        return 'שגיאה בשירות, נסה שוב מאוחר יותר'

def generate_market_report(report_type='morning'):
    if report_type == 'morning':
        prompt = 'כתוב דוח בוקר קצר על שוק ההון. כלול S&P500, נאסד\'ק, דאו ג\'ונס. חתום: hotstocks. סיים: אין בנכתב המלצה לקניה/מכירה של ניירות ערך'
    else:
        prompt = 'כתוב דוח סגירה קצר על שוק ההון. כלול ביצועי המדדים ומניות מובילות. חתום: hotstocks. סיים: אין בנכתב המלצה לקניה/מכירה של ניירות ערך'
    return call_gemini(prompt, max_tokens=800)

def send_telegram(text, chat_id=None):
    cid = chat_id or TELEGRAM_CHAT_ID
    if not cid or not TELEGRAM_BOT_TOKEN:
        logger.error('Missing chat_id or token')
        return
    url = 'https://api.telegram.org/bot' + TELEGRAM_BOT_TOKEN + '/sendMessage'
    try:
        r = requests.post(url, json={'chat_id': cid, 'text': text}, timeout=10)
        logger.info('Telegram send status: %s', r.status_code)
    except Exception as e:
        logger.error('Telegram error: %s', str(e))

def send_morning_report():
    logger.info('Sending morning report')
    send_telegram(generate_market_report('morning'))

def send_closing_report():
    logger.info('Sending closing report')
    send_telegram(generate_market_report('closing'))

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        if data and 'message' in data:
            cid = str(data['message']['chat']['id'])
            text = data['message'].get('text', '')
            logger.info('Received: %s from %s', text, cid)
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
scheduler.add_job(send_morning_report, 'cron', day_of_week='sun-thu', hour=9, minute=15)
scheduler.add_job(send_closing_report, 'cron', day_of_week='sun-thu', hour=23, minute=30)
scheduler.start()
logger.info('Scheduler started')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

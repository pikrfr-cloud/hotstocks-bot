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

MODELS = [
    'gemini-2.5-flash',
    'gemini-2.0-flash',
    'gemini-2.0-flash-001',
    'gemini-2.0-flash-lite-001',
]

SIGN = '\nhotstocks\nאין בנכתב המלצה לקניה/מכירה של ניירות ערך'


def build_prompt(user_text, report_type=None):
    footer = 'hotstocks\nאין בנכתב המלצה לקניה/מכירה של ניירות ערך'
    if report_type == 'morning':
        return (
            'כתוב דוח בוקר קצר לשוק ההון הישראלי והעולמי. '
            'עברית בלבד, ללא אמוגים, מקצועי. '
            f'בסיום כתוב בדיוק:\n{footer}'
        )
    if report_type == 'closing':
        return (
            'כתוב דוח סגירה קצר לשוק ההון הישראלי והעולמי. '
            'עברית בלבד, ללא אמוגים, מקצועי. '
            f'בסיום כתוב בדיוק:\n{footer}'
        )
    return (
        'אתה בוט שוק ההון בסגנון הוט סטוק. '
        'ענה תמיד בעברית בלבד, ללא אמוגים, קצר ומקצועי. '
        'אם ההודעה לא ברורה - פרש אותה כשאלה על שוק ההון וענה. '
        f'בסיום כתוב בדיוק:\n{footer}\n\n'
        f'הודעה: {user_text}'
    )


def call_gemini(prompt, max_tokens=2000):
    if not GEMINI_API_KEY:
        return 'שגיאה: מפתח API חסר'
    for model in MODELS:
        url = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}'
        # For gemini-2.5-flash, disable thinking to save tokens
        if '2.5' in model:
            data = {
                'contents': [{'parts': [{'text': prompt}]}],
                'generationConfig': {
                    'maxOutputTokens': max_tokens,
                    'thinkingConfig': {'thinkingBudget': 0}
                }
            }
        else:
            data = {
                'contents': [{'parts': [{'text': prompt}]}],
                'generationConfig': {'maxOutputTokens': max_tokens}
            }
        try:
            resp = requests.post(url, json=data, timeout=60)
            logger.info('Gemini %s: %s', model, resp.status_code)
            if resp.status_code == 200:
                text = resp.json()['candidates'][0]['content']['parts'][0]['text']
                if 'hotstocks' not in text:
                    text += SIGN
                return text
            elif resp.status_code in (429, 503):
                logger.warning('Unavailable on %s (%s), trying next', model, resp.status_code)
                continue
            else:
                logger.error('Error on %s: %s', model, resp.text[:100])
                continue
        except Exception as e:
            logger.error('Exception on %s: %s', model, str(e))
            continue
    return 'שירות אי זמין רגע, נסה שוב מאוחר'


def send_telegram(text, chat_id=None):
    cid = chat_id or TELEGRAM_CHAT_ID
    if not cid or not TELEGRAM_BOT_TOKEN:
        return
    url = 'https://api.telegram.org/bot' + TELEGRAM_BOT_TOKEN + '/sendMessage'
    try:
        r = requests.post(url, json={'chat_id': cid, 'text': text}, timeout=10)
        logger.info('Telegram: %s', r.status_code)
    except Exception as e:
        logger.error('Telegram error: %s', str(e))


def send_morning_report():
    send_telegram(call_gemini(build_prompt(None, 'morning'), max_tokens=2000))


def send_closing_report():
    send_telegram(call_gemini(build_prompt(None, 'closing'), max_tokens=2000))


@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        if data and 'message' in data:
            cid = str(data['message']['chat']['id'])
            text = data['message'].get('text', '')
            logger.info('Msg from %s: %s', cid, text[:80])
            if text:
                prompt = build_prompt(text)
                resp = call_gemini(prompt, max_tokens=2000)
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

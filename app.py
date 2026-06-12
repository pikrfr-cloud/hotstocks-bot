import os
import anthropic
import requests
from flask import Flask, request
from apscheduler.schedulers.background import BackgroundScheduler
import pytz

app = Flask(__name__)

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """אתה שירות מידע על שוק ההון בסגנון הוט סטוק.
כתוב בעברית בלבד, ללא אמוג'י.
הסגנון: עובדתי, מספרי, תמציתי.
חתום תמיד: hotstocks
הוסף תמיד בסוף: אין בנכתב המלצה לקניה/מכירה של ניירות ערך"""

def generate_market_report(report_type='morning'):
    if report_type == 'morning':
        prompt = 'כתוב דוח בוקר לשוק המניות האמריקאי. כלול: S&P500, נאסד, דאו - מגמה צפויה.'
    else:
        prompt = 'כתוב דוח סגירה לשוק המניות האמריקאי. כלול: ביצועי מדדים, מניות מובילות.'
    msg = anthropic_client.messages.create(
        model='claude-opus-4-5',
        max_tokens=500,
        messages=[{'role': 'user', 'content': prompt}],
        system=SYSTEM_PROMPT
    )
    return msg.content[0].text

def send_telegram(text, chat_id=None):
    cid = chat_id or TELEGRAM_CHAT_ID
    if not cid or not TELEGRAM_BOT_TOKEN:
        return
    requests.post(f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage',
                  json={'chat_id': cid, 'text': text})

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
            resp = anthropic_client.messages.create(
                model='claude-opus-4-5',
                max_tokens=300,
                messages=[{'role': 'user', 'content': text}],
                system=SYSTEM_PROMPT
            )
            send_telegram(resp.content[0].text, chat_id=cid)
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

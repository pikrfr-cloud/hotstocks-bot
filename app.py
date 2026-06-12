import os
import anthropic
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from apscheduler.schedulers.background import BackgroundScheduler
from twilio.rest import Client
import datetime
import pytz

app = Flask(__name__)

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_WHATSAPP_NUMBER = os.environ.get('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886')
RECIPIENT_WHATSAPP = os.environ.get('RECIPIENT_WHATSAPP')

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """אתה שירות מידע על שוק ההון בסגנון הוט סטוק.
כתוב בעברית בלבד, ללא אמוג'י.
הסגנון: עובדתי, מספרי, תמציתי.
חתום תמיד: hotstocks
הוסף תמיד בסוף: אין בנכתב המלצה לקניה/מכירה של ניירות ערך
דוח בוקר: סקירת מדדים מרכזיים, מגמה, מניות מובילות.
דוח סגירה: סיכום יומי עם נתונים.
תשובות לשאלות: קצרות, עובדתיות, עם מספרים."""

def generate_market_report(report_type="morning"):
    if report_type == "morning":
        prompt = "כתוב דוח בוקר לשוק המניות האמריקאי. כלול: מדד S&P500, נאסד, דאו גונס - מגמה צפויה, חדשות מרכזיות."
    else:
        prompt = "כתוב דוח סגירה לשוק המניות האמריקאי. כלול: ביצועי מדדים מרכזיים, מניות מובילות, סיכום מגמה."
    
    message = anthropic_client.messages.create(
        model="claude-opus-4-5",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
        system=SYSTEM_PROMPT
    )
    return message.content[0].text

def send_whatsapp_message(body, to=None):
    if not to:
        to = RECIPIENT_WHATSAPP
    if not to:
        return
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    client.messages.create(body=body, from_=TWILIO_WHATSAPP_NUMBER, to=to)

def send_morning_report():
    report = generate_market_report("morning")
    send_whatsapp_message(report)

def send_closing_report():
    report = generate_market_report("closing")
    send_whatsapp_message(report)

@app.route('/webhook', methods=['POST'])
def webhook():
    incoming_msg = request.values.get('Body', '').strip()
    resp = MessagingResponse()
    msg = resp.message()
    if incoming_msg:
        response = anthropic_client.messages.create(
            model="claude-opus-4-5",
            max_tokens=300,
            messages=[{"role": "user", "content": incoming_msg}],
            system=SYSTEM_PROMPT
        )
        msg.body(response.content[0].text)
    else:
        msg.body("שלום! אני בוט מידע על שוק ההון. שאל אותי כל שאלה על מניות ומדדים.")
    return str(resp)

@app.route('/health', methods=['GET'])
def health():
    return "OK", 200

if __name__ == '__main__':
    israel_tz = pytz.timezone('Asia/Jerusalem')
    scheduler = BackgroundScheduler(timezone=israel_tz)
    scheduler.add_job(send_morning_report, 'cron', day_of_week='sun-thu', hour=9, minute=15)
    scheduler.add_job(send_closing_report, 'cron', day_of_week='sun-thu', hour=23, minute=30)
    scheduler.start()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

import os
import json
import smtplib
import imaplib
import email
from email.mime.text import MIMEText
from email.header import decode_header

from gemini_core import gemini_request

EMAIL_ADDRESS = os.environ.get("EMAIL_ADDRESS", "")
EMAIL_APP_PASSWORD = os.environ.get("EMAIL_APP_PASSWORD", "")

bot = None  # يتحدد من assistant.py

EMAIL_SEND_KEYWORDS = ["ابعت ايميل", "ابعت إيميل", "ابعتل ايميل", "send email"]
EMAIL_READ_KEYWORDS = ["قريتلي ايميلاتي", "إيميلاتي", "ايميلاتي", "قري ايميلاتي", "قريت الايميلات", "قريت الإيميلات"]

def handle_email_text(user_id, user_text):
    if not EMAIL_ADDRESS or not EMAIL_APP_PASSWORD:
        return None  # الإيميل متظبطش — نتجاهل

    # 📬 قراءة الإيميلات
    if any(k in user_text for k in EMAIL_READ_KEYWORDS):
        if "قريتلي" in user_text or "قري" in user_text:
            return read_inbox_summary()
        return "قول: «قريتلي ايميلاتي» وهفتحلك البريد 📬"

    # ✉️ إرسال إيميل
    if any(k in user_text for k in EMAIL_SEND_KEYWORDS):
        return process_send_request(user_text)

    return None

def parse_email_request(text):
    """جيميناي يستخرج تفاصيل الإيميل من كلام المستخدم"""
    prompt = f"""المستخدم عايز يبعت إيميل. رسالته: "{text}"

استخرج ورجّع JSON فقط (بدون markdown):
{{"to": "إيميل المستلم كما ذكره المستلم", "subject": "موضوع مناسب", "body": "نص الإيميل كامل جاهز للإرسال، مكتوب باحترافية بالعربي"}}
لو مفيش إيميل واضح في الرسالة، خلي "to" فاضي."""
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    result = gemini_request(body)
    raw = result["candidates"][0]["content"]["parts"][0]["text"].strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(raw)
    except:
        return None

def send_email(to, subject, body_text):
    msg = MIMEText(body_text, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        server.send_message(msg)

def process_send_request(user_text):
    data = parse_email_request(user_text)
    if not data:
        return "مش فهمت الطلب 😅 قولها زي كده: ابعت ايميل لـ example@gmail.com وقوله كذا"

    to = data.get("to", "").strip()
    if not to or "@" not in to:
        return "محتاج إيميل المستلم صريح 📧\nمثال: ابعت ايميل لـ ahmed@gmail.com وقوله إني هغيب بكرة"

    subject = data.get("subject", "رسالة")
    body_text = data.get("body", "")

    try:
        send_email(to, subject, body_text)
        return (f"✅ **بعت الإيميل بنجاح!**\n\n"
                f"📨 إلى: {to}\n"
                f"📌 الموضوع: {subject}\n"
                f"📝 نص الإيميل:\n{body_text}")
    except Exception as e:
        print("🔴 خطأ في الإرسال:", e)
        return "⚠️ فشل الإرسال — اتأكد من App Password في start.sh وجرب تاني"

def read_inbox_summary():
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        mail.select("INBOX")

        status, data = mail.search(None, "ALL")
        ids = data[0].split()[-5:]  # آخر 5 إيميلات

        msgs = []
        for i in reversed(ids):
            status, msg_data = mail.fetch(i, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])

                    # الموضوع
                    subject = ""
                    if msg.get("Subject"):
                        for text, enc in decode_header(msg["Subject"]):
                            if isinstance(text, bytes):
                                subject += text.decode(enc or "utf-8", errors="replace")
                            else:
                                subject += text
                    else:
                        subject = "(بدون موضوع)"

                    from_ = msg.get("From", "")
                    date_ = msg.get("Date", "")

                    # جزء من النص
                    body_text = ""
                    try:
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        body_text = payload.decode(errors="replace")[:250]
                                        break
                        else:
                            payload = msg.get_payload(decode=True)
                            if payload:
                                body_text = payload.decode(errors="replace")[:250]
                    except:
                        pass

                    msgs.append(f"📨 من: {from_}\n📌 {subject}\n🕐 {date_}\n📝 {body_text}...\n")

        mail.logout()

        if not msgs:
            return "📬 الـ Inbox فاضي — مفيش إيميلات"

        return "📬 آخر إيميلاتك:\n\n" + "\n".join(msgs)

    except Exception as e:
        print("🔴 خطأ في القراءة:", e)
        return "⚠️ فشلت قراءة الإيميلات — اتأكد من App Password في start.sh"

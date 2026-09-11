import os
import re
import json
import requests
from datetime import datetime, timedelta

from gemini_core import gemini_request

CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
REDIRECT_URI = "http://localhost:1"
SCOPES = "https://www.googleapis.com/auth/calendar"
TOKEN_FILE = "token.json"

bot = None

CAL_ADD_KEYWORDS = ["حط ميعاد", "ضيف ميعاد", "اضف ميعاد", "سجل ميعاد", "حط موعد", "ضيف موعد", "سجل موعد"]
CAL_VIEW_KEYWORDS = ["مواعيدي", "مواعيد", "جدولي", "التقويم بتاعي"]

def is_connected():
    return os.path.exists(TOKEN_FILE)

def get_access_token():
    if not is_connected():
        return None
    with open(TOKEN_FILE) as f:
        token = json.load(f)
    try:
        r = requests.post("https://oauth2.googleapis.com/token", data={
            "refresh_token": token.get("refresh_token"),
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token"
        })
        if r.status_code == 200:
            return r.json().get("access_token")
    except Exception as e:
        print("🔴 خطأ تجديد التوكن:", e)
    return None

def build_auth_url():
    return (
        "https://accounts.google.com/o/oauth2/auth?"
        f"client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        "&response_type=code"
        f"&scope={SCOPES}"
        "&access_type=offline"
        "&prompt=consent"
    )

def exchange_code(auth_code):
    try:
        r = requests.post("https://oauth2.googleapis.com/token", data={
            "code": auth_code,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code"
        })
        data = r.json()
        if "refresh_token" in data:
            with open(TOKEN_FILE, "w") as f:
                json.dump({"refresh_token": data["refresh_token"]}, f)
            return True
        print("🔴 فشل التبادل:", data)
    except Exception as e:
        print("🔴 خطأ التبادل:", e)
    return False

def api_request(method, path, body=None, params=None):
    token = get_access_token()
    if not token:
        return None, "🔗 التقويم مش مربوط — قول: «اربط التقويم»"
    url = f"https://www.googleapis.com/calendar/v3/calendars/primary/{path}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        r = requests.request(method, url, headers=headers, json=body,
                              params=params, timeout=20)
        if r.status_code in (200, 201):
            return r.json(), None
        print("🔴 جوجل رجع خطأ:", r.text[:300])
        return None, "⚠️ جوجل رجع خطأ — جرب تاني"
    except Exception as e:
        print("🔴 خطأ الاتصال:", e)
        return None, "⚠️ مشكلة اتصال بجوجل"

def parse_event_request(text):
    now = datetime.now()
    prompt = f"""المستخدم عايز يضيف ميعاد في التقويم. الوقت الحالي: {now.strftime('%Y-%m-%d %H:%M (%A)')}
رسالته: "{text}"

رد بـ JSON فقط:
{{"title": "عنوان مختصر للميعاد", "start": "YYYY-MM-DDTHH:MM", "duration_minutes": 60}}
لو المدة مش مذكورة: 60 دقيقة"""
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    result = gemini_request(body)
    raw = result["candidates"][0]["content"]["parts"][0]["text"].strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(raw)
    except:
        return None

def add_event(title, start_str, duration_minutes=60):
    try:
        start_dt = datetime.fromisoformat(start_str)
    except:
        return "⚠️ الوقت مش مفهوم — قوله زي: حط ميعاد بكرة 5 العصر"
    end_dt = start_dt + timedelta(minutes=duration_minutes or 60)

    body = {
        "summary": title,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "Africa/Cairo"},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": "Africa/Cairo"}
    }
    result, err = api_request("POST", "events", body=body)
    if err:
        return err
    return (f"📅 ✅ ضفت الميعاد في تقويم جوجل بتاعك:\n"
            f"📌 {title}\n"
            f"🕐 {start_dt.strftime('%Y-%m-%d — الساعة %H:%M')}\n"
            f"⏱️ المدة: {duration_minutes or 60} دقيقة")

def list_events(period="today"):
    now = datetime.now().astimezone()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "tomorrow":
        start = start + timedelta(days=1)
        end = start + timedelta(days=1)
        label = "بكرة"
    elif period == "week":
        end = start + timedelta(days=7)
        label = "الأسبوع الجاي"
    else:
        end = start + timedelta(days=1)
        label = "النهاردة"

    params = {
        "timeMin": start.isoformat(),
        "timeMax": end.isoformat(),
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": 25
    }
    result, err = api_request("GET", "events", params=params)
    if err:
        return err
    items = result.get("items", [])
    if not items:
        return f"📅 مفيش مواعيد {label} — يوم صافي 🙂"
    lines = []
    for ev in items:
        start_info = ev.get("start", {}).get("dateTime", "")
        try:
            dt = datetime.fromisoformat(start_info)
            when = dt.strftime("%d/%m الساعة %H:%M")
        except:
            when = start_info
        lines.append(f"📌 {ev.get('summary', '(بدون عنوان)')} — {when}")
    return f"📅 مواعيدك {label}:\n" + "\n".join(lines)

def handle_calendar_text(user_id, user_text):
    if not CLIENT_ID or not CLIENT_SECRET:
        return None  # التقويم متظبطش

    # 🔗 ربط التقويم
    if "اربط التقويم" in user_text:
        if is_connected():
            return "✅ التقويم مربوط خلاص!"
        url = build_auth_url()
        return ("🔗 **اضغط على اللينك ده** (انسخه وافتحه في المتصفح):\n\n"
                f"{url}\n\n"
                " الخطوات:\n"
                "1️⃣ سجل بحساب جوجل بتاعك\n"
                "2️⃣ هيظهر تحذير «التطبيق مش موثق» → اضغط Continue/Advanced → Go to assistant\n"
                "3️⃣ وافق على الصلاحيات ✅\n"
                "4️⃣ المتصفح هيحاول يفتح صفحة وهيفشل — **ده طبيعي ومتقلقش**\n"
                "5️⃣ انسخ **الرابط من شريط العنوان** (شكله: http://localhost:1/?code=4/0A...)\n"
                "6️⃣ ابعتلي الرابط هنا زي ما هو 📋")

    # 📋 استلام رابط الربط
    if "localhost" in user_text and "code=" in user_text:
        m = re.search(r"code=([^&\s]+)", user_text)
        if m:
            if exchange_code(m.group(1)):
                return "🎉 تم ربط التقويم بنجاح!\nجرّب: «إيه مواعيدي النهاردة؟»"
            return "⚠️ الكود مظبطش — قول «اربط التقويم» وابعت الرابط من الأول"
        return "الرابط ناقص الكود — انسخه كامل من شريط العنوان"

    # مطلوب تقويم وهو مش مربوط؟
    if not is_connected():
        for kw in CAL_ADD_KEYWORDS + CAL_VIEW_KEYWORDS:
            if kw in user_text:
                return "🔗 التقويم لسه مش مربوط — قول: «اربط التقويم» الأول"
        return None

    # 👀 عرض المواعيد
    if any(k in user_text for k in CAL_VIEW_KEYWORDS):
        if "بكرة" in user_text or "بكره" in user_text or "الغد" in user_text:
            return list_events("tomorrow")
        if "أسبوع" in user_text or "اسبوع" in user_text or "الجاي" in user_text:
            return list_events("week")
        return list_events("today")

    # ➕ إضافة ميعاد
    if any(k in user_text for k in CAL_ADD_KEYWORDS):
        data = parse_event_request(user_text)
        if not data:
            return "مش فهمت الميعاد 😅 قوله زي: حط ميعاد بكرة 5 العصر اسمه اجتماع الفريق"
        return add_event(data["title"], data["start"], data.get("duration_minutes", 60))

    return None

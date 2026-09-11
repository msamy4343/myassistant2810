import json
import threading
from datetime import datetime, timedelta

from memory_store import reminders, save
from gemini_core import gemini_request

bot = None  # يتحدد من assistant.py

REMINDER_KEYWORDS = ["فكرني", "فكرنى", "ذكرني", "ذكرنى", "ذكّرني", "ذكّرنى"]

def is_reminder_request(text):
    return any(k in text for k in REMINDER_KEYWORDS)

def parse_reminder(text):
    now = datetime.now()
    prompt = f"""المستخدم طلب تذكير. الوقت الحالي: {now.strftime('%Y-%m-%d %H:%M')}
رسالة المستخدم: "{text}"

رد بـ JSON فقط بدون شرح:
{{"text": "نص التذكير المختصر بدون كلمة فكرني", "minutes": <عدد الدقايق من دلوقتي>, "repeat": "none"}}

لو طلب تكرار يومي (كل يوم/يومياً): "repeat": "daily"
لو الوقت مش واضح خالص: {{"text": "", "minutes": -1, "repeat": "none"}}"""

    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    result = gemini_request(body)
    raw = result["candidates"][0]["content"]["parts"][0]["text"].strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        data = json.loads(raw)
        return data.get("text", ""), int(data.get("minutes", -1)), data.get("repeat", "none")
    except:
        return "", -1, "none"

def fire_reminder(r):
    try:
        if bot:
            bot.send_message(r["chat_id"], f"⏰ تذكير: {r['text']}")
    except Exception as e:
        print("خطأ في إرسال التذكير:", e)

    # 🔁 لو تذكير يومي — نعيد جدولته بعد إرساله
    if r.get("repeat") == "daily":
        schedule_reminder(r["chat_id"], 24 * 60, r["text"], "daily")

    reminders[:] = [x for x in reminders if x["id"] != r["id"]]
    save("reminders", reminders)

def schedule_reminder(chat_id, minutes, text, repeat="none"):
    reminder_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
    fire_at = datetime.now() + timedelta(minutes=minutes)
    entry = {
        "id": reminder_id,
        "chat_id": chat_id,
        "text": text,
        "fire_at": fire_at.isoformat(),
        "repeat": repeat
    }
    reminders.append(entry)
    save("reminders", reminders)

    timer = threading.Timer(minutes * 60, fire_reminder, args=[entry])
    timer.daemon = True
    timer.start()
    return fire_at

def restore_reminders():
    now = datetime.now()
    pending = []
    for r in reminders:
        try:
            fire_time = datetime.fromisoformat(r["fire_at"])
            diff = (fire_time - now).total_seconds()
            if diff < 0:
                diff = 3
            timer = threading.Timer(diff, fire_reminder, args=[r])
            timer.daemon = True
            timer.start()
            pending.append(r)
        except Exception as e:
            print("تذكير بايظ:", e)
    reminders[:] = pending
    save("reminders", reminders)
    if pending:
        print(f"⏰ رجّعت {len(pending)} تذكير محفوظ")

def handle_reminders_text(user_id, user_text):
    """يرجع رد لو الرسالة عن التذكيرات — وإلا None"""
    if "تذكيراتي" in user_text or "التذكيرات" in user_text:
        if "امسح" in user_text or "الغ" in user_text:
            reminders.clear()
            save("reminders", reminders)
            return "🗑️ مسحت كل التذكيرات."
        if not reminders:
            return "مفيش أي تذكيرات مجدولة دلوقتي 🙂"
        lines = []
        for r in reminders:
            rep = " (يومي 🔁)" if r.get("repeat") == "daily" else ""
            lines.append(f"• {r['text']} — الساعة {datetime.fromisoformat(r['fire_at']).strftime('%H:%M')}{rep}")
        return "⏰ تذكيراتك:\n" + "\n".join(lines)

    if is_reminder_request(user_text):
        text, minutes, repeat = parse_reminder(user_text)
        if minutes < 0:
            return "الوقت مش واضح 😅 قولي بالظبط إمتى — مثلاً: فكرني الساعة 8 مساءً"
        fire_at = schedule_reminder(user_id, minutes, text, repeat)
        rep_txt = " كل يوم 🔁" if repeat == "daily" else ""
        return f"⏰ تمام! هفكرك بـ «{text}» الساعة {fire_at.strftime('%H:%M')}{rep_txt}"

    return None

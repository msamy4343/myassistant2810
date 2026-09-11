import threading
from datetime import datetime, timedelta

from memory_store import tasks, save, state, reminders
from gemini_core import gemini_request
from config import MORNING_BRIEF_HOUR

bot = None  # يتحدد من assistant.py

TASKS_ADD = ["ضيف مهمة", "ضيف لمهامي", "ضيفلي مهمة", "ضيف ليا مهمة", "اضف مهمة"]
TASKS_DONE = ["خلصت", "أنجزت", "انجزت", "عملتها"]

def handle_tasks_text(user_id, user_text):
    """يرجع رد لو الرسالة عن المهام — وإلا None"""

    if "مهامي" in user_text:
        if "امسح" in user_text or "الغ" in user_text:
            tasks.clear()
            save("tasks", tasks)
            return "🗑️ مسحت كل المهام."
        if not tasks:
            return "مفيش مهام دلوقتي 📋\nقوللي: «ضيف مهمة: كذا»"
        lines = []
        for i, t in enumerate(tasks, 1):
            mark = "✅" if t["done"] else "⬜"
            lines.append(f"{mark} {i}. {t['text']}")
        done_count = len([t for t in tasks if t["done"]])
        return f"📋 مهامك ({done_count} من {len(tasks)} خلصت):\n" + "\n".join(lines)

    for kw in TASKS_ADD:
        if kw in user_text:
            task_text = user_text.split(kw, 1)[1].strip(" :：:-")
            if not task_text:
                return "اكتب المهمة بعد الأمر — مثلاً: ضيف مهمة اذاكر 3 فصول"
            tasks.append({"text": task_text, "date": datetime.now().strftime("%Y-%m-%d %H:%M"), "done": False})
            save("tasks", tasks)
            return f"✅ ضفت المهمة: {task_text}"

    for kw in TASKS_DONE:
        if kw in user_text:
            done_text = user_text.split(kw, 1)[1].strip(" :：")
            for t in tasks:
                if not t["done"] and done_text and (done_text in t["text"] or t["text"] in done_text):
                    t["done"] = True
                    save("tasks", tasks)
                    remaining = len([x for x in tasks if not x["done"]])
                    return f"🎉 برافو! خلصت: {t['text']}\n(فاضل {remaining} مهام)"
            if tasks:
                lines = "\n".join(f"{'✅' if t['done'] else '⬜'} {t['text']}" for t in tasks)
                return "مش لاقي المهمة دي 🤔 دي مهامك:\n" + lines + "\nقول: خلصت + اسم المهمة"

    return None

# 🌅 ====== الملخص الصباحي ======
def send_morning_brief():
    try:
        chat_id = state.get("owner_chat_id")
        if not chat_id:
            return

        pending = [t["text"] for t in tasks if not t["done"]]
        todays_reminders = [r["text"] for r in reminders]

        parts = [f"☀️ صباح الخير يا مصطفى!\n📅 {datetime.now().strftime('%A %d/%m')}"]

        if pending:
            parts.append("📋 مهامك النهاردة:\n" + "\n".join(f"⬜ {t}" for t in pending))
        else:
            parts.append("📋 مفيش مهام معلقة — يوم صافي! 😄")

        if todays_reminders:
            parts.append("⏰ تذكيراتك:\n" + "\n".join(f"• {r}" for r in todays_reminders))

        # جملة تحفيزية من جيميناي
        body = {"contents": [{"role": "user", "parts": [{"text": "اكتب جملة تحفيزية قصيرة واحدة بالعربي لبداية يوم موفق"}]}]}
        result = gemini_request(body)
        quote = result["candidates"][0]["content"]["parts"][0]["text"].strip()
        parts.append(f"💪 {quote}")

        if bot:
            bot.send_message(chat_id, "\n\n".join(parts))
    except Exception as e:
        print("خطأ في الملخص الصباحي:", e)
    finally:
        schedule_next_brief()

def schedule_next_brief():
    now = datetime.now()
    next_run = now.replace(hour=MORNING_BRIEF_HOUR, minute=0, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)
    diff = (next_run - now).total_seconds()
    t = threading.Timer(diff, send_morning_brief)
    t.daemon = True
    t.start()
    print(f"🌅 الملخص الصباحي مجدول: {next_run.strftime('%Y-%m-%d %H:%M')}")

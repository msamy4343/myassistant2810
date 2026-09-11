# ====== 🤖 مساعدي الشخصي — النسخة الشاملة النهائية ======
import telebot

from config import TELEGRAM_TOKEN
from gemini_core import gemini_request
from memory_store import memory, save, state, knowledge

import tools_reminders
import tools_tasks
import tools_files
import tools_email
import tools_calendar
import tools_search
import tools_audio
import skills
import tools_memory

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ربط البوت بالأدوات
tools_reminders.bot = bot
tools_tasks.bot = bot
tools_files.bot = bot
tools_email.bot = bot
tools_calendar.bot = bot


def process_message(user_id, user_text):
    # 0️⃣ تسجيل صاحب البوت (عشان الملخص الصباحي)
    if not state.get("owner_chat_id"):
        state["owner_chat_id"] = user_id
        save("state", state)

    # 1️⃣ ملفاتي
    r = tools_files.handle_files_text(user_id, user_text)
    if r: return r

    # 2️⃣ التذكيرات (أولوية — عشان "فكرني...")
    r = tools_reminders.handle_reminders_text(user_id, user_text)
    if r: return r

    # 3️⃣ المهام
    r = tools_tasks.handle_tasks_text(user_id, user_text)
    if r: return r

    # 4️⃣ الأوضاع 🎭
    r = skills.handle_mode_text(user_text)
    if r: return r

    # 5️⃣ ملخص Word للمحادثة
    if tools_files.is_word_request(user_text):
        return tools_files.make_conversation_word(user_id, user_id)

    # 6️⃣ الإيميل 📧
    r = tools_email.handle_email_text(user_id, user_text)
    if r: return r

    # 7️⃣ التقويم 📅
    r = tools_calendar.handle_calendar_text(user_id, user_text)
    if r: return r

    # 8️⃣ لينك → تلخيص
    if tools_search.is_link(user_text):
        return tools_search.summarize_link(user_text)

    # 9️⃣ بحث في الإنترنت
    if tools_search.needs_search(user_text):
        return tools_search.search_and_answer(user_text)

    # 🔟 إدارة الذاكرة 🧠
    r = tools_memory.handle_memory_text(user_id, user_text)
    if r: return r

    # 1️⃣1️⃣ محادثة عادية (بالوض

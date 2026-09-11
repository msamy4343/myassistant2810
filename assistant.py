# ====== 🤖 مساعدي الشخصي — النسخة الشاملة ======
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

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ربط البوت بالأدوات
tools_reminders.bot = bot
tools_tasks.bot = bot
tools_files.bot = bot
tools_email.bot = bot
tools_calendar.bot = bot

def ask_gemini(history, user_message, personality):
    contents = []
    for msg in history:
        contents.append({"role": msg["role"], "parts": [{"text": msg["content"]}]})
    contents.append({"role": "user", "parts": [{"text": user_message}]})
    body = {
        "system_instruction": {"parts": [{"text": personality}]},
        "contents": contents
    }
    result = gemini_request(body)
    return result["candidates"][0]["content"]["parts"][0]["text"]

def process_message(user_id, user_text):
    # تسجيل صاحب البوت (عشان الملخص الصباحي)
    if not state.get("owner_chat_id"):
        state["owner_chat_id"] = user_id
        save("state", state)

    # 1️⃣ القوائم
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
        
    # 5️⃣ الإيميل 📧
    r = tools_email.handle_email_text(user_id, user_text)
    if r: return r  

    # 6️⃣ التقويم 📅
    r = tools_calendar.handle_calendar_text(user_id, user_text)
    if r: return r

    # 6️⃣ لينك → تلخيص
    if tools_search.is_link(user_text):
        return tools_search.summarize_link(user_text)

    # 7️⃣ بحث في الإنترنت
    if tools_search.needs_search(user_text):
        return tools_search.search_and_answer(user_text)

    # 8️⃣ محادثة عادية (بالوضع الحالي + سياق الملفات)
    if user_id not in memory:
        memory[user_id] = []
    history = memory[user_id][-30:]

    message_with_context = user_text
    for name, info in knowledge.items():
        if name in user_text:
            context = f"\n\n[معرفتك من ملف «{name}»:\nالملخص: {info['summary']}\nجزء من النص:\n{info.get('text', '')[:8000]}]"
            message_with_context += context
            break

    personality = skills.get_current_personality()
    reply = ask_gemini(history, message_with_context, personality)

    memory[user_id].append({"role": "user", "content": user_text})
    memory[user_id].append({"role": "model", "content": reply})
    save("memory", memory)
    return reply

# ====== الـ Handlers ======

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message,
        "أهلاً يا مصطفى! 👋 أنا مساعدك الشامل:\n\n"
        "💬 اكتبلي أي حاجة\n"
        "🎤 ابعتلي فويس (هرد فويس!)\n"
        "⏰ فكرني... / فكرني كل يوم...\n"
        "📋 ضيف مهمة... / مهامي؟\n"
        "📁 ابعتلي ملف أو صورة\n"
        "🔍 دور على... أو ابعتلي لينك\n"
        "🎭 حط وضع: مدرس / سكرتير / صديق / مدرب\n\n"
        "/مسح — مسح الذاكرة")

@bot.message_handler(commands=['مسح'])
def reset(message):
    memory[str(message.chat.id)] = []
    save("memory", memory)
    bot.reply_to(message, "✅ مسحت الذاكرة — بداية جديدة!")

@bot.message_handler(content_types=['document'])
def on_document(message):
    tools_files.handle_document(message)

@bot.message_handler(content_types=['photo'])
def on_photo(message):
    tools_files.handle_photo(message)

@bot.message_handler(func=lambda m: m.content_type == 'text' and not m.text.startswith('/'))
def chat(message):
    user_id = str(message.chat.id)
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        reply = process_message(user_id, message.text)
        if reply:
            bot.reply_to(message, reply)
    except Exception as e:
        print("خطأ:", e)
        bot.reply_to(message, "⚠️ حصل خطأ، جرب تاني")

@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    user_id = str(message.chat.id)
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        file_info = bot.get_file(message.voice.file_id)
        ogg_bytes = bot.download_file(file_info.file_path)

        user_text = tools_audio.voice_to_text(ogg_bytes)
        print("🎤 قلت:", user_text)

        reply = process_message(user_id, user_text)

        if reply:
            bot.send_chat_action(message.chat.id, 'record_voice')
            tools_audio.send_audio_reply(bot, message.chat.id, reply)
    except Exception as e:
        print("خطأ في الصوت:", e)
        bot.reply_to(message, "⚠️ حصل خطأ، ابعتها تاني")

# 🚀 الإقلاع
tools_reminders.restore_reminders()
tools_tasks.schedule_next_brief()
print("🤖 المساعد الشامل شغال! (نص + صوت فويس + تذكيرات + مهام + ملفات + بحث + أوضاع 🎭)")
bot.infinity_polling()

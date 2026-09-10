# ====== 🤖 مساعدي الشخصي — نسخة الصوت 🎤 ======
import telebot
import requests
import json
import os
import io
import base64
import asyncio
import edge_tts

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

bot = telebot.TeleBot(TELEGRAM_TOKEN)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key=" + GEMINI_API_KEY

# 🗣️ صوت الرد (رجالي مصري)
TTS_VOICE = "ar-EG-ShakirNeural"

PERSONALITY = """أنت "مساعدي" — مساعد شخصي عربي ذكي.
صاحبك اسمه مصطفى،
قواعدك:
- ردودك ودودة ومباشرة بدون مقدمات طويلة
- لما تشرح حاجة: اشرح بالتفصيل مع أمثلة عملية
- لما يطلب تنفيذ حاجة: نفذها كاملة وجاهزة
- افتكر تفاصيل حياته واستخدمها لما تنفع
- الردود في المكالمات الصوتية تكون مختصرة وطبيعية زي الكلام
"""

MEMORY_FILE = "memory.json"

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_memory():
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)

memory = load_memory()

def gemini_request(body):
    r = requests.post(GEMINI_URL, json=body)
    result = r.json()
    if "error" in result:
        error_msg = result["error"].get("message", "خطأ غير معروف")
        print("🔴 خطأ من جيميناي:", error_msg)
        raise Exception(error_msg)
    return result

def ask_gemini(history, user_message):
    contents = []
    for msg in history:
        contents.append({"role": msg["role"], "parts": [{"text": msg["content"]}]})
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    body = {
        "system_instruction": {"parts": [{"text": PERSONALITY}]},
        "contents": contents
    }

    result = gemini_request(body)
    return result["candidates"][0]["content"]["parts"][0]["text"]

# 🎤 صوت → نص (عن طريق جيميناي)
def voice_to_text(ogg_bytes):
    audio_b64 = base64.b64encode(ogg_bytes).decode()
    body = {
        "contents": [{
            "parts": [
                {"text": "حوّل الرسالة الصوتية دي لنص مكتوب. اكتب النص فقط من غير أي تعليق إضافي."},
                {"inline_data": {"mime_type": "audio/ogg", "data": audio_b64}}
            ]
        }]
    }
    result = gemini_request(body)
    return result["candidates"][0]["content"]["parts"][0]["text"].strip()

# 🔊 نص → صوت (صوت مصري طبيعي)
def text_to_speech_file(text):
    async def _make():
        communicate = edge_tts.Communicate(text, TTS_VOICE)
        await communicate.save("reply.mp3")
    asyncio.run(_make())
    audio = io.BytesIO(open("reply.mp3", "rb").read())
    audio.name = "reply.mp3"
    return audio

# 💾 المسار المشترك للمحادثة (نص أو صوت)
def process_message(user_id, user_text):
    if user_id not in memory:
        memory[user_id] = []
    history = memory[user_id][-30:]

    reply = ask_gemini(history, user_text)

    memory[user_id].append({"role": "user", "content": user_text})
    memory[user_id].append({"role": "model", "content": reply})
    save_memory()
    return reply

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message,
        "أهلاً يا مصطفى! 👋 أنا مساعدك الشخصي.\n\n"
        "ابعتلي رسالة نص 📝 أو فويس 🎤 — وأنا هفهمك وأرد عليك.\n\n"
        "/مسح — مسح الذاكرة والبدء من جديد")

@bot.message_handler(commands=['مسح'])
def reset(message):
    memory[str(message.chat.id)] = []
    save_memory()
    bot.reply_to(message, "✅ مسحت الذاكرة — بداية جديدة!")

# 📝 المسار النصي
@bot.message_handler(func=lambda m: m.content_type == 'text')
def chat(message):
    user_id = str(message.chat.id)
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        reply = process_message(user_id, message.text)
        bot.reply_to(message, reply)
    except Exception as e:
        print("خطأ:", e)
        bot.reply_to(message, "⚠️ حصل خطأ، جرب تاني")

# 🎤 المسار الصوتي
@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    user_id = str(message.chat.id)
    try:
        bot.send_chat_action(message.chat.id, 'typing')

        # 1. ننزل الفويس
        file_info = bot.get_file(message.voice.file_id)
        ogg_bytes = bot.download_file(file_info.file_path)
        print("📥 فويس وصلت...")

        # 2. صوت → نص
        user_text = voice_to_text(ogg_bytes)
        print("📝 اللي قلته:", user_text)

        # 3. المحادثة + الذاكرة
        reply = process_message(user_id, user_text)

        # 4. نص → صوت → إرسال
        bot.send_chat_action(message.chat.id, 'record_voice')
        audio = text_to_speech_file(reply)
        bot.send_audio(message.chat.id, audio)

    except Exception as e:
        print("خطأ في الصوت:", e)
        bot.reply_to(message, "⚠️ حصل خطأ في الصوت، ابعتها تاني")

print("🤖 المساعد شغال (نص + صوت 🎤)!")
bot.infinity_polling()

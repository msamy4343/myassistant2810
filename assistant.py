# ====== 🤖 مساعدي الشخصي — النسخة السحابية ======
import telebot
from google import genai
from flask import Flask
import threading
import json
import os

# ⚙️ المفاتيح بتتقرا من متغيرات البيئة (آمنة)
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

bot = telebot.TeleBot(TELEGRAM_TOKEN)
ai = genai.Client(api_key=GEMINI_API_KEY)

# 🧠 شخصية المساعد
PERSONALITY = """أنت "مساعدي" — مساعد شخصي عربي ذكي.
صاحبك اسمه مصطفى، مشغول بـ: شغل + دراسة + مشروع.
قواعدك:
- ردودك ودودة ومباشرة بدون مقدمات طويلة
- لما تشرح حاجة: اشرح بالتفصيل مع أمثلة عملية
- لما يطلب تنفيذ حاجة: نفذها كاملة وجاهزة
- افتكر تفاصيل حياته واستخدمها لما تنفع
"""

# 💾 الذاكرة
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

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message,
        "أهلاً يا مصطفى! 👋 أنا مساعدك الشخصي.\n\n"
        "اكتبلي أي حاجة — سؤال، طلب، أو كلام عادي.\n"
        "أنا هفتكر محادثاتنا عشان أعرفك أكتر.\n\n"
        "/مسح — مسح الذاكرة والبدء من جديد")

@bot.message_handler(commands=['مسح'])
def reset(message):
    memory[str(message.chat.id)] = []
    save_memory()
    bot.reply_to(message, "✅ مسحت الذاكرة — بداية جديدة!")

@bot.message_handler(func=lambda m: True)
def chat(message):
    user_id = str(message.chat.id)

    if user_id not in memory:
        memory[user_id] = []

    history = memory[user_id][-30:]

    contents = []
    for msg in history:
        contents.append({"role": msg["role"], "parts": [{"text": msg["content"]}]})
    contents.append({"role": "user", "parts": [{"text": message.text}]})

    try:
        bot.send_chat_action(message.chat.id, 'typing')

        response = ai.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
            config={"system_instruction": PERSONALITY}
        )
        reply = response.text

        memory[user_id].append({"role": "user", "content": message.text})
        memory[user_id].append({"role": "model", "content": reply})
        save_memory()

        bot.reply_to(message, reply)

    except Exception as e:
        print("خطأ:", e)
        bot.reply_to(message, "⚠️ حصل خطأ، جرب تبعت رسالتك تاني")

# 🌐 سيرفر صغير عشان السيرفر السحابي يفضل شغال
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 المساعد شغال!"

def run_flask():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

def run_bot():
    bot.infinity_polling()

print("🤖 المساعد شغال! روح تيليجرام واكتب للبوت")
threading.Thread(target=run_flask, daemon=True).start()
run_bot()

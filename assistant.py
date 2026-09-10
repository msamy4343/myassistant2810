import telebot
import requests
import json
import os

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

bot = telebot.TeleBot(TELEGRAM_TOKEN)

PERSONALITY = """أنت "مساعدي" — مساعد شخصي عربي ذكي.
صاحبك اسمه مصطفى، مشغول بـ: شغل + دراسة + مشروع.
قواعدك:
- ردودك ودودة ومباشرة بدون مقدمات طويلة
- لما تشرح حاجة: اشرح بالتفصيل مع أمثلة عملية
- لما يطلب تنفيذ حاجة: نفذها كاملة وجاهزة
- افتكر تفاصيل حياته واستخدمها لما تنفع
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

def ask_gemini(history, user_message):
    contents = []
    for msg in history:
        contents.append({"role": msg["role"], "parts": [{"text": msg["content"]}]})
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key=" + GEMINI_API_KEY

    body = {
        "system_instruction": {"parts": [{"text": PERSONALITY}]},
        "contents": contents
    }

    r = requests.post(url, json=body)
    result = r.json()

    if "error" in result:
        error_msg = result["error"].get("message", "خطأ غير معروف")
        print("🔴 خطأ من جيميناي:", error_msg)
        raise Exception(error_msg)

    return result["candidates"][0]["content"]["parts"][0]["text"]

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message,
        "أهلاً يا مصطفى! 👋 أنا مساعدك الشخصي.\n\n"
        "اكتبلي أي حاجة — سؤال، طلب، أو كلام عادي.\n\n"
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

    try:
        bot.send_chat_action(message.chat.id, 'typing')
        reply = ask_gemini(history, message.text)

        memory[user_id].append({"role": "user", "content": message.text})
        memory[user_id].append({"role": "model", "content": reply})
        save_memory()

        bot.reply_to(message, reply)

    except Exception as e:
        print("خطأ:", e)
        bot.reply_to(message, "⚠️ حصل خطأ، جرب تبعت رسالتك تاني")

print("🤖 Hi mostafa")
bot.infinity_polling()

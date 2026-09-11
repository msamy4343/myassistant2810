import os
import json
from datetime import datetime

from gemini_core import gemini_request
from memory_store import memory, save

FACTS_FILE = "facts.json"
SUMMARIES_FILE = "summaries.json"
MEMORY_WINDOW = 30   # الرسايل الحية
EXTRACT_EVERY = 5    # استخراج الحقائق كل كام رسالة

def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

facts = load_json(FACTS_FILE, [])
summaries = load_json(SUMMARIES_FILE, [])

# ====== استخراج الحقائق ======
def extract_facts_from(messages):
    convo = "\n".join([("المستخدم: " if m["role"] == "user" else "المساعد: ") + m["content"] for m in messages])
    prompt = f"""دي محادثة بين مصطفى ومساعده الشخصي:

{convo}

استخرج أي حقائق دائمة ومهمة عن مصطفى (شغله، دراسته، مشروعه، عاداته، تفضيلاته، أسماء ناس مهمين عنده، أهدافه، ظروفه).
رد بـ JSON array فقط — كل حقيقة سطر قصير:
["حقيقة 1", "حقيقة 2"]
لو مفيش حقائق جديدة تستاهل الحفظ: رد []"""
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    result = gemini_request(body)
    raw = result["candidates"][0]["content"]["parts"][0]["text"].strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(raw)
    except:
        return []

def add_facts(new_facts):
    added = 0
    for f in new_facts:
        if isinstance(f, str):
            f = f.strip()
            if len(f) < 5:
                continue
            if any(f in old["fact"] or old["fact"] in f for old in facts):
                continue  # مكرر
            facts.append({"fact": f, "date": datetime.now().strftime("%Y-%m-%d")})
            added += 1
    if added:
        save_json(FACTS_FILE, facts)
    return added

def consolidate_facts():
    """دمج الحقائق لو كتروا (شيل التكرار)"""
    if len(facts) < 25:
        return
    all_facts = "\n".join([f"- {f['fact']}" for f in facts])
    prompt = f"""دي قاائمة حقائق عن مصطفى — ادمج المتشابهات واختصر واشيل التكرار:
{all_facts}

رد بالقايمة المدمجة فقط — كل حقيقة في سطر يبدأ بـ -"""
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    result = gemini_request(body)
    text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
    new_list = [l.lstrip("-• ").strip() for l in text.split("\n") if l.strip() and l.strip()[:1] in "-•"]
    if new_list:
        facts.clear()
        for f in new_list:
            facts.append({"fact": f, "date": datetime.now().strftime("%Y-%m-%d")})
        save_json(FACTS_FILE, facts)
        print(f"🧠 دمجت الحقائق — بقى {len(facts)} حقيقة")

# ====== ضغط المحادثات القديمة ======
def compress_old_messages(user_id):
    msgs = memory.get(user_id, [])
    if len(msgs) <= MEMORY_WINDOW + 10:
        return
    try:
        old = msgs[:-MEMORY_WINDOW]
        convo = "\n".join([("م: " if m["role"] == "user" else "ا: ") + m["content"] for m in old])
        prompt = f"لخص المحادثة دي في نقاط مختصرة تحفظ أهم المعلومات والقرارات:\n{convo[:12000]}"
        body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        result = gemini_request(body)
        summary = result["candidates"][0]["content"]["parts"][0]["text"].strip()
        summaries.append({
            "summary": summary,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "msg_count": len(old)
        })
        save_json(SUMMARIES_FILE, summaries)
        memory[user_id] = msgs[-MEMORY_WINDOW:]
        save("memory", memory)
        print("📖 لخصت الرسايل القديمة")
    except Exception as e:
        print("مشكلة الضغط:", e)

def maybe_extract_and_compress(user_id):
    """بيتنادى بعد كل رد — استخراج + ضغط"""
    msgs = memory.get(user_id, [])
    # 1. استخراج حقائق كل 5 رسايل
    if len(msgs) > 0 and len(msgs) % EXTRACT_EVERY == 0:
        try:
            new_facts = extract_facts_from(msgs[-6:])
            if new_facts:
                added = add_facts(new_facts)
                if added:
                    print(f"🧠 حفظت {added} حقيقة جديدة")
                consolidate_facts()
        except Exception as e:
            print("مشكلة استخراج الحقائق:", e)
    # 2. ضغط
    compress_old_messages(user_id)

# ====== بناء السياق الكامل ======
def build_context_messages(user_id, current_text):
    if user_id not in memory:
        memory[user_id] = []
    msgs = memory[user_id][-MEMORY_WINDOW:]

    contents = []

    # حقن الحقائق + الملخص كجزء من المحادثة
    context_parts = []
    if facts:
        facts_text = "\n".join([f"• {f['fact']}" for f in facts[-40:]])
        context_parts.append(f"حقائق محفوظة عن مصطفى:\n{facts_text}")
    if summaries:
        s_text = summaries[-1]["summary"]
        context_parts.append(f"ملخص آخر محادثة قديمة بينكم:\n{s_text}")

    if context_parts:
        contents.append({"role": "user", "parts": [{"text": "عرض عليّ كل اللي بتفتكره عني قبل ما نكمل"}]})
        contents.append({"role": "model", "parts": [{"text": "اللي بحفظه:\n\n" + "\n\n".join(context_parts)}]})

    for m in msgs:
        contents.append({"role": m["role"], "parts": [{"text": m["content"]}]})
    contents.append({"role": "user", "parts": [{"text": current_text}]})
    return contents

# ====== أوامر إدارة الذاكرة ======
def handle_memory_text(user_id, user_text):
    if "بتفتكره عني" in user_text or "حقائقي" in user_text or "تعرفه عني" in user_text or "اللي بتعرفه" in user_text:
        if not facts:
            return "🧠 لسه بحفظ حاجات قليلة عنك — اتكلم معايا أكتر وهتعلم عنك أوتوماتيك!"
        lines = [f"• {f['fact']}" for f in facts]
        return f"🧠 اللي بحفظه عنك ({len(facts)} حقيقة):\n" + "\n".join(lines)

    if "انسى كل حاجة" in user_text or "امسح ذاكرتك" in user_text or "امسح كل الذاكرات" in user_text:
        facts.clear()
        summaries.clear()
        save_json(FACTS_FILE, facts)
        save_json(SUMMARIES_FILE, summaries)
        memory[user_id] = []
        save("memory", memory)
        return "🧹 مسحت كل طبقات الذاكرة — صفحة جديدة خالص."

    return None

import requests
from bs4 import BeautifulSoup
from gemini_core import gemini_request

SEARCH_KEYWORDS = [
    "دور على", "دور لي", "دورلي", "ابحث عن", "ابحث لي", "ابحثلي",
    "بحث عن", "آخر أخبار", "اخبار", "أخبار", "سعر", "أسعار", "اسعار",
    "طقس", "الطقس", "الجو بكرة", "الجو النهاردة"
]

def needs_search(text):
    return any(k in text for k in SEARCH_KEYWORDS)

def is_link(text):
    return "http://" in text or "https://" in text or "www." in text

def web_search(query, max_results=6):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        }
        r = requests.post("https://html.duckduckgo.com/html/",
                          data={"q": query}, headers=headers, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        results = []
        for res in soup.select("div.result")[:max_results]:
            title_el = res.select_one("a.result__a")
            snippet_el = res.select_one(".result__snippet")
            if title_el:
                results.append({
                    "title": title_el.get_text(strip=True),
                    "url": title_el.get("href", ""),
                    "snippet": snippet_el.get_text(strip=True) if snippet_el else ""
                })
        return results
    except Exception as e:
        print("🔴 خطأ في البحث:", e)
        return []

def search_and_answer(user_text):
    results = web_search(user_text)
    if not results:
        return "😔 معرفش ألاقي نتايج دلوقتي — جرب تاني بعد شوية."

    context = "\n\n".join([
        f"عنوان: {r['title']}\nملخص: {r['snippet']}\nالرابط: {r['url']}"
        for r in results
    ])

    prompt = f"""المستخدم سأل: "{user_text}"

دورت في الإنترنت ولقيت:

{context}

لخص الإجابة بالعربي بطريقة واضحة ومنظمة. اذكر المصادر في الآخر."""
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    result = gemini_request(body)
    return result["candidates"][0]["content"]["parts"][0]["text"]

def summarize_link(user_text):
    """يبعت رابط → يقراه ويلخصه"""
    url = None
    for word in user_text.split():
        if is_link(word):
            url = word.strip("()<>,")
            break
    if not url:
        return None
    try:
        if not url.startswith("http"):
            url = "https://" + url
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        page_text = soup.get_text(separator="\n", strip=True)
        title = soup.title.string.strip() if soup.title and soup.title.string else url

        prompt = f"لخص الصفحة دي بالعربي في نقاط واضحة:\nالعنوان: {title}\n\n{page_text[:15000]}"
        body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        result = gemini_request(body)
        return f"📄 لخصت «{title}»:\n\n" + result["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print("🔴 خطأ في اللينك:", e)
        return "😔 معرفش أفتح الرابط ده — تأكد منه وجرب تاني"

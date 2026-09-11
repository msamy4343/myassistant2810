import requests
from config import GEMINI_URL

def gemini_request(body):
    r = requests.post(GEMINI_URL, json=body)
    result = r.json()
    if "error" in result:
        error_msg = result["error"].get("message", "خطأ غير معروف")
        print("🔴 خطأ من جيميناي:", error_msg)
        raise Exception(error_msg)
    return result

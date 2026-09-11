import io
import os
import base64
import asyncio
import subprocess

import edge_tts
from config import TTS_VOICE
from gemini_core import gemini_request

def voice_to_text(ogg_bytes):
    audio_b64 = base64.b64encode(ogg_bytes).decode()
    body = {
        "contents": [{
            "parts": [
                {"text": "حوّل الرسالة الصوتية دي لنص مكتوب. اكتب النص فقط."},
                {"inline_data": {"mime_type": "audio/ogg", "data": audio_b64}}
            ]
        }]
    }
    result = gemini_request(body)
    return result["candidates"][0]["content"]["parts"][0]["text"].strip()

def text_to_speech(text):
    """يرجع (bytes, filename, is_voice) — OGG لو ffmpeg موجود"""
    async def _make():
        communicate = edge_tts.Communicate(text, TTS_VOICE)
        await communicate.save("reply.mp3")
    asyncio.run(_make())

    mp3 = open("reply.mp3", "rb").read()

    # 🎙️ التحويل لفويس نوت حقيقي
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", "reply.mp3", "-c:a", "libopus", "-b:a", "64k", "reply.ogg"],
            check=True, capture_output=True
        )
        ogg = open("reply.ogg", "rb").read()
        return ogg, "reply.ogg", True
    except Exception as e:
        print("ffmpeg مش متاح — هنستخدم mp3:", e)
        return mp3, "reply.mp3", False

def send_audio_reply(bot, chat_id, text):
    data, filename, is_voice = text_to_speech(text)
    audio = io.BytesIO(data)
    audio.name = filename
    if is_voice:
        bot.send_voice(chat_id, audio)
    else:
        bot.send_audio(chat_id, audio)

import json
import os

FILES = {
    "memory": "memory.json",
    "reminders": "reminders.json",
    "knowledge": "files.json",
    "tasks": "tasks.json",
    "state": "state.json",
}

def load(name, default):
    path = FILES[name]
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save(name, data):
    with open(FILES[name], "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# الحالات المشتركة بين كل الملفات
memory = load("memory", {})
reminders = load("reminders", [])
knowledge = load("knowledge", {})
tasks = load("tasks", [])
state = load("state", {"mode": "عادي", "owner_chat_id": None})

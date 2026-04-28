import json
import os
from collections import Counter
from datetime import datetime

from assistant_memory import get_session_context


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_TASKS_FILE = os.path.join(BASE_DIR, "brain", "knowledge_tasks.json")
TRACKED_TOPICS = ("biotech", "career", "nursing", "study", "exam", "fitness", "diet", "python", "project")


def _now():
    return datetime.now().isoformat(timespec="seconds")


def ensure_knowledge_task_storage():
    os.makedirs(os.path.dirname(KNOWLEDGE_TASKS_FILE), exist_ok=True)
    if not os.path.exists(KNOWLEDGE_TASKS_FILE):
        with open(KNOWLEDGE_TASKS_FILE, "w", encoding="utf-8") as handle:
            json.dump({"tasks": []}, handle, ensure_ascii=False, indent=2)


def _load():
    ensure_knowledge_task_storage()
    try:
        with open(KNOWLEDGE_TASKS_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            data.setdefault("tasks", [])
            return data
    except Exception:
        pass
    return {"tasks": []}


def _save(data):
    ensure_knowledge_task_storage()
    with open(KNOWLEDGE_TASKS_FILE, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def enqueue_knowledge_task(topic, reason="knowledge_gap"):
    clean_topic = (topic or "").strip().lower()
    if not clean_topic:
        return None
    data = _load()
    tasks = data.get("tasks", [])
    if any((item.get("topic") or "").strip().lower() == clean_topic for item in tasks[-8:]):
        return None
    entry = {
        "created_at": _now(),
        "status": "queued",
        "topic": clean_topic,
        "reason": reason,
        "summary": f"Expand local understanding around {clean_topic} for future replies.",
    }
    tasks.append(entry)
    data["tasks"] = tasks[-30:]
    _save(data)
    return entry


def detect_repeated_topics(limit=20):
    text = "\n".join(get_session_context(limit=limit)).lower()
    counts = Counter(topic for topic in TRACKED_TOPICS if text.count(topic) >= 2)
    return [topic for topic, _ in counts.most_common(4)]


def update_knowledge_tasks_from_context():
    created = []
    for topic in detect_repeated_topics(limit=20):
        item = enqueue_knowledge_task(topic, reason="repeated_topic_interest")
        if item:
            created.append(item)
    return created

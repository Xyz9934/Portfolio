import json
import os
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REFLECTION_FILE = os.path.join(BASE_DIR, "reflection_log.json")


def _load():
    try:
        with open(REFLECTION_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _save(items):
    with open(REFLECTION_FILE, "w", encoding="utf-8") as handle:
        json.dump(items[-40:], handle, ensure_ascii=False, indent=2)


def score_response(user_text, reply_text):
    score = 1.0
    reply = (reply_text or "").strip()
    user = (user_text or "").strip().lower()

    if not reply:
        score -= 0.7
    if len(reply) < 18:
        score -= 0.2
    if "i couldn't" in reply.lower() or "not available" in reply.lower():
        score -= 0.25
    if any(word in user for word in ("tired", "sad", "nervous", "frustrated")) and "take care" not in reply.lower() and "breathe" not in reply.lower():
        score -= 0.15

    return max(0.0, min(1.0, score))


def log_reflection(user_text, reply_text):
    items = _load()
    score = score_response(user_text, reply_text)
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "user": user_text,
        "reply": reply_text[:500],
        "score": score,
    }
    items.append(entry)
    _save(items)
    return entry

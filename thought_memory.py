import json
import os
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
THOUGHT_DIR = os.path.join(BASE_DIR, "brain", "thoughts")
THOUGHT_LOG_FILE = os.path.join(THOUGHT_DIR, "reasoning_logs.json")


def _now():
    return datetime.now().isoformat(timespec="seconds")


def ensure_thought_memory_storage():
    os.makedirs(THOUGHT_DIR, exist_ok=True)
    if not os.path.exists(THOUGHT_LOG_FILE):
        with open(THOUGHT_LOG_FILE, "w", encoding="utf-8") as handle:
            json.dump({"items": []}, handle, ensure_ascii=False, indent=2)


def _load():
    ensure_thought_memory_storage()
    try:
        with open(THOUGHT_LOG_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            data.setdefault("items", [])
            return data
    except Exception:
        pass
    return {"items": []}


def _save(data):
    ensure_thought_memory_storage()
    with open(THOUGHT_LOG_FILE, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def log_reasoning_trace(user_input, draft_answer="", final_answer="", critique="", confidence=0.0, alternatives=None):
    data = _load()
    item = {
        "timestamp": _now(),
        "user_input": (user_input or "").strip(),
        "draft_answer": (draft_answer or "").strip(),
        "final_answer": (final_answer or "").strip(),
        "critique": (critique or "").strip(),
        "confidence": float(confidence or 0.0),
        "alternatives": [entry for entry in (alternatives or []) if entry],
    }
    data["items"].append(item)
    data["items"] = data["items"][-60:]
    _save(data)
    return item


def get_recent_reasoning_patterns(limit=5):
    items = _load().get("items", [])[-limit:]
    patterns = []
    for item in items:
        user_input = item.get("user_input", "").strip()
        critique = item.get("critique", "").strip()
        if user_input:
            patterns.append(f"Recent reasoning case: {user_input}")
        if critique:
            patterns.append(f"Critique learned: {critique}")
    return patterns[: limit * 2]


def summarize_thought_patterns(limit=10):
    items = _load().get("items", [])[-limit:]
    if not items:
        return ""

    low_conf = sum(1 for item in items if float(item.get("confidence") or 0.0) < 0.55)
    critique_count = sum(1 for item in items if item.get("critique"))
    if low_conf == 0 and critique_count == 0:
        return "Recent thinking has been stable."
    return (
        f"Recent background reflection: {critique_count} critiques recorded, "
        f"{low_conf} lower-confidence answers worth extra caution."
    )

import json
import os
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FEEDBACK_FILE = os.path.join(BASE_DIR, "brain", "execution_feedback.json")


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _ensure():
    os.makedirs(os.path.dirname(FEEDBACK_FILE), exist_ok=True)
    if not os.path.exists(FEEDBACK_FILE):
        with open(FEEDBACK_FILE, "w", encoding="utf-8") as handle:
            json.dump({"items": []}, handle, ensure_ascii=False, indent=2)


def _load():
    _ensure()
    try:
        with open(FEEDBACK_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            data.setdefault("items", [])
            return data
    except Exception:
        pass
    return {"items": []}


def _save(data):
    _ensure()
    with open(FEEDBACK_FILE, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def log_execution_feedback(action_name, result_text, success=True):
    data = _load()
    data["items"].append(
        {
            "timestamp": _now(),
            "action_name": (action_name or "").strip(),
            "result_text": (result_text or "").strip(),
            "success": bool(success),
        }
    )
    data["items"] = data["items"][-80:]
    _save(data)


def get_execution_feedback_context(limit=5):
    items = _load().get("items", [])[-limit:]
    context = []
    for item in items:
        label = "success" if item.get("success") else "failure"
        action_name = item.get("action_name", "").strip()
        result_text = item.get("result_text", "").strip()
        if action_name or result_text:
            context.append(f"Execution feedback [{label}] {action_name}: {result_text}")
    return context

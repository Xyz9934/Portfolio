import json
import os
from datetime import datetime

from assistant_memory import get_session_context
from life_brain import get_active_goals


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INITIATIVE_FILE = os.path.join(BASE_DIR, "brain", "initiative_queue.json")


def _now():
    return datetime.now().isoformat(timespec="seconds")


def ensure_initiative_storage():
    os.makedirs(os.path.dirname(INITIATIVE_FILE), exist_ok=True)
    if not os.path.exists(INITIATIVE_FILE):
        with open(INITIATIVE_FILE, "w", encoding="utf-8") as handle:
            json.dump({"items": []}, handle, ensure_ascii=False, indent=2)


def _load():
    ensure_initiative_storage()
    try:
        with open(INITIATIVE_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            data.setdefault("items", [])
            return data
    except Exception:
        pass
    return {"items": []}


def _save(data):
    ensure_initiative_storage()
    with open(INITIATIVE_FILE, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def enqueue_initiative(message, reason="pattern_detected", priority=0.5):
    text = (message or "").strip()
    if not text:
        return None
    data = _load()
    items = data.get("items", [])
    if any((item.get("message") or "").strip().lower() == text.lower() for item in items[-5:]):
        return None
    entry = {
        "created_at": _now(),
        "reason": reason,
        "priority": float(priority or 0.0),
        "message": text,
    }
    items.append(entry)
    data["items"] = items[-20:]
    _save(data)
    return entry


def peek_initiative_suggestion():
    items = _load().get("items", [])
    if not items:
        return None
    return sorted(items, key=lambda item: float(item.get("priority") or 0.0), reverse=True)[0]


def generate_initiative_from_context():
    session_text = "\n".join(get_session_context(limit=12)).lower()
    goals = get_active_goals(limit=2)
    if not session_text and not goals:
        return None

    if session_text.count("career") + session_text.count("biotech") + session_text.count("study") >= 3:
        return enqueue_initiative(
            "FRIDAY Suggestion: You've been asking a lot about career direction. Want me to build a 30-day career roadmap next?",
            reason="career_pattern",
            priority=0.86,
        )
    if session_text.count("gym") + session_text.count("diet") + session_text.count("workout") >= 3:
        return enqueue_initiative(
            "FRIDAY Suggestion: Fitness keeps coming up. I can turn that into a simple weekly workout and diet rhythm if you want.",
            reason="fitness_pattern",
            priority=0.82,
        )
    if goals:
        goal_name = (goals[0].get("goal_name") or "").strip()
        if goal_name:
            return enqueue_initiative(
                f"FRIDAY Suggestion: Your active goal is {goal_name}. Want the smallest high-impact next step for today?",
                reason="goal_priority",
                priority=0.78,
            )
    if any(word in session_text for word in ("confused", "stuck", "unsure")):
        return enqueue_initiative(
            "FRIDAY Suggestion: You seem a bit stuck. I can narrow this down with one smart question first.",
            reason="confusion_signal",
            priority=0.74,
        )
    return None

import json
import os
from datetime import datetime

from assistant_memory import get_session_context
from life_brain import get_active_goals


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IDENTITY_FILE = os.path.join(BASE_DIR, "brain", "user_identity.json")


def _now():
    return datetime.now().isoformat(timespec="seconds")


def ensure_identity_storage():
    os.makedirs(os.path.dirname(IDENTITY_FILE), exist_ok=True)
    if not os.path.exists(IDENTITY_FILE):
        payload = {
            "updated_at": _now(),
            "risk_tolerance": "balanced",
            "discipline_level": "developing",
            "interests": [],
            "weaknesses": [],
            "goals": [],
        }
        with open(IDENTITY_FILE, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)


def load_user_identity():
    ensure_identity_storage()
    try:
        with open(IDENTITY_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {
        "updated_at": _now(),
        "risk_tolerance": "balanced",
        "discipline_level": "developing",
        "interests": [],
        "weaknesses": [],
        "goals": [],
    }


def save_user_identity(payload):
    ensure_identity_storage()
    data = payload or {}
    data["updated_at"] = _now()
    with open(IDENTITY_FILE, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def refresh_user_identity():
    session_items = "\n".join(get_session_context(limit=16)).lower()
    goals = get_active_goals(limit=5)
    goal_names = [(item.get("goal_name") or "").strip() for item in goals if item.get("goal_name")]
    identity = load_user_identity()

    interests = set(identity.get("interests") or [])
    weaknesses = set(identity.get("weaknesses") or [])

    if any(word in session_items for word in ("biotech", "career", "college", "study", "exam")):
        interests.update(["career", "study"])
    if any(word in session_items for word in ("gym", "fitness", "diet", "workout")):
        interests.update(["fitness"])
    if any(word in session_items for word in ("code", "python", "project", "debug")):
        interests.update(["coding"])
    if any(word in session_items for word in ("confused", "stuck", "unsure", "dont know", "don't know")):
        weaknesses.add("decision friction")
    if any(word in session_items for word in ("skip", "delay", "later", "tomorrow")):
        weaknesses.add("consistency drift")

    discipline = "high" if "consistency drift" not in weaknesses and "fitness" in interests else "developing"
    if "consistency drift" in weaknesses:
        discipline = "inconsistent"

    risk = "cautious" if any(word in session_items for word in ("safe", "stable", "secure")) else "balanced"
    identity.update(
        {
            "risk_tolerance": risk,
            "discipline_level": discipline,
            "interests": sorted(interests),
            "weaknesses": sorted(weaknesses),
            "goals": goal_names[:5],
        }
    )
    save_user_identity(identity)
    return identity


def render_identity_context():
    identity = load_user_identity()
    lines = []
    if identity.get("risk_tolerance"):
        lines.append(f"User identity: risk tolerance is {identity['risk_tolerance']}.")
    if identity.get("discipline_level"):
        lines.append(f"User identity: discipline level is {identity['discipline_level']}.")
    if identity.get("interests"):
        lines.append("User interests: " + ", ".join(identity["interests"][:5]) + ".")
    if identity.get("weaknesses"):
        lines.append("Likely friction points: " + ", ".join(identity["weaknesses"][:4]) + ".")
    if identity.get("goals"):
        lines.append("Current goals: " + ", ".join(identity["goals"][:4]) + ".")
    return lines

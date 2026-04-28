import json
import os
import sqlite3
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BRAIN_DIR = os.path.join(BASE_DIR, "brain")
USER_PROFILE_FILE = os.path.join(BRAIN_DIR, "user_profile.json")
HABITS_DB = os.path.join(BRAIN_DIR, "habits.db")
GOALS_DB = os.path.join(BRAIN_DIR, "goals.db")
DECISIONS_LOG = os.path.join(BRAIN_DIR, "decisions.log")


def _now():
    return datetime.now().isoformat(timespec="seconds")


def ensure_life_brain_storage():
    os.makedirs(BRAIN_DIR, exist_ok=True)
    if not os.path.exists(USER_PROFILE_FILE):
        _write_json(
            USER_PROFILE_FILE,
            {
                "identity": {},
                "preferences": {},
                "habits_summary": {},
                "strengths": [],
                "weaknesses": [],
                "schedules": {},
                "last_updated_at": _now(),
            },
        )
    _init_habits_db()
    _init_goals_db()
    if not os.path.exists(DECISIONS_LOG):
        with open(DECISIONS_LOG, "w", encoding="utf-8") as handle:
            handle.write("")


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def _read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(default, dict) and isinstance(data, dict):
            return data
    except Exception:
        pass
    return default


def _init_habits_db():
    with sqlite3.connect(HABITS_DB) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS habit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                habit_name TEXT NOT NULL,
                event_type TEXT NOT NULL,
                note TEXT DEFAULT '',
                occurred_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def _init_goals_db():
    with sqlite3.connect(GOALS_DB) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_name TEXT NOT NULL,
                status TEXT NOT NULL,
                roadmap TEXT DEFAULT '',
                progress_note TEXT DEFAULT '',
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS goal_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                goal_name TEXT NOT NULL,
                event_type TEXT NOT NULL,
                note TEXT DEFAULT '',
                occurred_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def load_user_profile():
    ensure_life_brain_storage()
    return _read_json(
        USER_PROFILE_FILE,
        {
            "identity": {},
            "preferences": {},
            "habits_summary": {},
            "strengths": [],
            "weaknesses": [],
            "schedules": {},
            "last_updated_at": _now(),
        },
    )


def save_user_profile(profile):
    ensure_life_brain_storage()
    profile["last_updated_at"] = _now()
    _write_json(USER_PROFILE_FILE, profile)


def update_profile_from_memory(memory_profile):
    ensure_life_brain_storage()
    current = load_user_profile()
    preferences = memory_profile.get("preferences", {})
    facts = memory_profile.get("facts", [])

    for key, value in preferences.items():
        if isinstance(value, dict):
            current.setdefault("preferences", {})[key] = value.get("value", "")

    for fact in facts:
        text = fact.get("text", "") if isinstance(fact, dict) else ""
        lowered = text.lower()
        if "goal:" in lowered:
            current.setdefault("identity", {})["goal_hint"] = text
        if "project:" in lowered:
            current.setdefault("identity", {})["project_hint"] = text

    save_user_profile(current)
    return current


def record_habit_event(habit_name, event_type="mentioned", note=""):
    ensure_life_brain_storage()
    with sqlite3.connect(HABITS_DB) as conn:
        conn.execute(
            "INSERT INTO habit_events (habit_name, event_type, note, occurred_at) VALUES (?, ?, ?, ?)",
            ((habit_name or "").strip(), (event_type or "mentioned").strip(), (note or "").strip(), _now()),
        )
        conn.commit()


def set_goal(goal_name, roadmap="", progress_note="", status="active"):
    cleaned_goal = (goal_name or "").strip()
    if not cleaned_goal:
        return
    ensure_life_brain_storage()
    with sqlite3.connect(GOALS_DB) as conn:
        row = conn.execute("SELECT id FROM goals WHERE goal_name = ?", (cleaned_goal,)).fetchone()
        if row:
            conn.execute(
                "UPDATE goals SET status = ?, roadmap = ?, progress_note = ?, updated_at = ? WHERE goal_name = ?",
                (status, roadmap, progress_note, _now(), cleaned_goal),
            )
        else:
            conn.execute(
                "INSERT INTO goals (goal_name, status, roadmap, progress_note, updated_at) VALUES (?, ?, ?, ?, ?)",
                (cleaned_goal, status, roadmap, progress_note, _now()),
            )
        conn.execute(
            "INSERT INTO goal_events (goal_name, event_type, note, occurred_at) VALUES (?, ?, ?, ?)",
            (cleaned_goal, "updated", progress_note or roadmap[:300], _now()),
        )
        conn.commit()


def get_active_goals(limit=5):
    ensure_life_brain_storage()
    with sqlite3.connect(GOALS_DB) as conn:
        rows = conn.execute(
            "SELECT goal_name, status, progress_note, updated_at FROM goals WHERE status != 'done' ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        {
            "goal_name": row[0],
            "status": row[1],
            "progress_note": row[2],
            "updated_at": row[3],
        }
        for row in rows
    ]


def get_goal_roadmap(goal_name):
    ensure_life_brain_storage()
    with sqlite3.connect(GOALS_DB) as conn:
        row = conn.execute(
            "SELECT roadmap FROM goals WHERE goal_name = ? ORDER BY updated_at DESC LIMIT 1",
            ((goal_name or "").strip(),),
        ).fetchone()
    return row[0] if row and row[0] else ""


def log_decision(user_input, reply_text, intent="", decision_type="response"):
    ensure_life_brain_storage()
    entry = {
        "timestamp": _now(),
        "intent": intent,
        "decision_type": decision_type,
        "user_input": (user_input or "").strip(),
        "reply": (reply_text or "").strip()[:800],
    }
    with open(DECISIONS_LOG, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def get_recent_decisions(limit=5):
    ensure_life_brain_storage()
    if not os.path.exists(DECISIONS_LOG):
        return []
    rows = []
    with open(DECISIONS_LOG, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows[-limit:]


def get_life_brain_context(limit=6):
    ensure_life_brain_storage()
    profile = load_user_profile()
    lines = []

    for key, value in profile.get("preferences", {}).items():
        if value:
            lines.append(f"Life brain - Preference: {key} = {value}")

    for goal in get_active_goals(limit=3):
        goal_name = goal.get("goal_name", "")
        progress = goal.get("progress_note", "")
        lines.append(f"Life brain - Active goal: {goal_name}")
        if progress:
            lines.append(f"Life brain - Goal progress: {progress}")

    for decision in get_recent_decisions(limit=2):
        user_input = decision.get("user_input", "")
        reply = decision.get("reply", "")
        if user_input:
            lines.append(f"Life brain - Decision history user: {user_input}")
        if reply:
            lines.append(f"Life brain - Decision history FRIDAY: {reply[:180]}")

    return lines[:limit]

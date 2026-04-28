import json
import os
import re
import threading
import uuid
from datetime import datetime, timedelta

from memory_guard import is_relevant_match, score_match

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_FILE = os.path.join(BASE_DIR, "assistant_profile.json")
TASKS_FILE = os.path.join(BASE_DIR, "assistant_tasks.json")
SUMMARIES_FILE = os.path.join(BASE_DIR, "assistant_summaries.json")
SESSION_MEMORY_FILE = os.path.join(BASE_DIR, "assistant_session_memory.json")
LIFE_THREADS_FILE = os.path.join(BASE_DIR, "life_threads.json")
FEEDBACK_MEMORY_FILE = os.path.join(BASE_DIR, "assistant_feedback_memory.json")
LOG_FILE = os.path.join(BASE_DIR, "friday_learning_log.jsonl")
TASKS_LOCK = threading.RLock()


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _now_dt():
    return datetime.now()


def _parse_iso_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(default, dict) and isinstance(data, dict):
            return data
        if isinstance(default, list) and isinstance(data, list):
            return data
    except Exception:
        pass
    return default


def _save_json(path, data):
    with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)


def _parse_time_fragment(text):
    cleaned = (text or "").strip().lower()
    if not cleaned:
        return None

    for fmt in ("%I %p", "%I:%M %p", "%H:%M", "%H"):
        try:
            return datetime.strptime(cleaned, fmt).time()
        except ValueError:
            continue
    return None


def parse_due_text(due_text):
    cleaned = (due_text or "").strip()
    if not cleaned:
        return "", "", ""

    now = _now_dt()
    lowered = cleaned.lower()
    due_date = now.date()
    due_time = None

    time_match = re.search(
        r"\bat\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b|(?<![\d-])(\d{1,2}:\d{2}\s*(?:am|pm)?|\d{1,2}\s*(?:am|pm))(?![\d-])",
        lowered,
    )
    if time_match:
        due_time = _parse_time_fragment(time_match.group(1) or time_match.group(2))

    iso_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", lowered)
    if iso_match:
        try:
            due_date = datetime.strptime(iso_match.group(1), "%Y-%m-%d").date()
        except ValueError:
            pass
    elif "tomorrow" in lowered:
        due_date = now.date() + timedelta(days=1)
    elif "today" in lowered:
        due_date = now.date()

    if due_time is None:
        if "tomorrow" in lowered:
            due_time = datetime.strptime("09:00", "%H:%M").time()
        elif "today" in lowered:
            due_time = (now + timedelta(minutes=30)).time().replace(second=0, microsecond=0)
        else:
            return cleaned, "", ""

    due_at = datetime.combine(due_date, due_time).replace(second=0, microsecond=0)
    remind_at = due_at - timedelta(minutes=15)
    return cleaned, due_at.isoformat(timespec="seconds"), remind_at.isoformat(timespec="seconds")


def ensure_assistant_storage():
    if not os.path.exists(PROFILE_FILE):
        _save_json(PROFILE_FILE, {"preferences": {}, "facts": []})
    if not os.path.exists(TASKS_FILE):
        _save_json(TASKS_FILE, [])
    if not os.path.exists(SUMMARIES_FILE):
        _save_json(SUMMARIES_FILE, [])
    if not os.path.exists(SESSION_MEMORY_FILE):
        _save_json(SESSION_MEMORY_FILE, [])
    if not os.path.exists(LIFE_THREADS_FILE):
        _save_json(LIFE_THREADS_FILE, {"gym_progress": [], "studies": [], "projects": [], "goals": []})
    if not os.path.exists(FEEDBACK_MEMORY_FILE):
        _save_json(FEEDBACK_MEMORY_FILE, [])


def load_profile():
    ensure_assistant_storage()
    profile = _load_json(PROFILE_FILE, {"preferences": {}, "facts": []})
    profile.setdefault("preferences", {})
    profile.setdefault("facts", [])
    return profile


def save_profile(profile):
    ensure_assistant_storage()
    _save_json(PROFILE_FILE, profile)


def set_preference(key, value):
    profile = load_profile()
    profile["preferences"][key] = {
        "value": value.strip(),
        "updated_at": _now(),
    }
    save_profile(profile)
    return profile["preferences"][key]


def add_fact(text):
    cleaned = (text or "").strip()
    if not cleaned:
        return False

    profile = load_profile()
    facts = profile["facts"]
    if cleaned not in [fact.get("text", "") for fact in facts if isinstance(fact, dict)]:
        facts.append({"text": cleaned, "created_at": _now()})
        save_profile(profile)
        return True
    return False


def get_profile_snapshot():
    profile = load_profile()
    lines = []

    preferences = profile.get("preferences", {})
    for key, value in preferences.items():
        if isinstance(value, dict):
            lines.append(f"Preference - {key}: {value.get('value', '')}")

    for fact in profile.get("facts", []):
        if isinstance(fact, dict) and fact.get("text"):
            lines.append(f"Fact - {fact['text']}")

    return lines


def load_tasks():
    with TASKS_LOCK:
        ensure_assistant_storage()
        tasks = _load_json(TASKS_FILE, [])
        normalized = []
        for task in tasks:
            if not isinstance(task, dict):
                continue
            task.setdefault("details", "")
            task.setdefault("due", "")
            task.setdefault("due_at", "")
            task.setdefault("remind_at", "")
            task.setdefault("reminder_sent_at", "")
            task.setdefault("recurrence", "")
            task.setdefault("status", "open")
            task.setdefault("created_at", _now())
            task.setdefault("completed_at", "")
            normalized.append(task)
        return normalized


def save_tasks(tasks):
    with TASKS_LOCK:
        ensure_assistant_storage()
        _save_json(TASKS_FILE, tasks)


def add_task(title, due_text="", details="", recurrence=""):
    cleaned = (title or "").strip(" .")
    if not cleaned:
        return None

    due_label, due_at, remind_at = parse_due_text(due_text)
    tasks = load_tasks()
    task = {
        "id": uuid.uuid4().hex[:8],
        "title": cleaned,
        "details": (details or "").strip(),
        "due": due_label,
        "due_at": due_at,
        "remind_at": remind_at,
        "reminder_sent_at": "",
        "recurrence": (recurrence or "").strip().lower(),
        "status": "open",
        "created_at": _now(),
        "completed_at": "",
    }
    tasks.append(task)
    save_tasks(tasks)
    return task


def find_best_task(query, include_done=False):
    cleaned_query = (query or "").strip()
    if not cleaned_query:
        return None, None, 0.0

    tasks = load_tasks()
    best_task = None
    best_score = 0.0

    for task in tasks:
        if not include_done and task.get("status") == "done":
            continue
        title = task.get("title", "")
        if not title:
            continue
        if cleaned_query.lower() in title.lower():
            score = 2.0
        else:
            score, _, _ = score_match(cleaned_query, title)
        if score > best_score:
            best_score = score
            best_task = task

    return tasks, best_task, best_score


def complete_task(query):
    tasks, best_task, best_score = find_best_task(query)
    if best_task is None or best_score < 0.45:
        return None

    if best_task.get("recurrence"):
        rolled = rollover_recurring_task(best_task)
        save_tasks(tasks)
        return rolled

    best_task["status"] = "done"
    best_task["completed_at"] = _now()
    save_tasks(tasks)
    return best_task


def reschedule_task(query, due_text):
    tasks, best_task, best_score = find_best_task(query)
    if best_task is None or best_score < 0.45:
        return None

    due_label, due_at, remind_at = parse_due_text(due_text)
    if not due_label:
        return None

    best_task["due"] = due_label
    best_task["due_at"] = due_at
    best_task["remind_at"] = remind_at
    best_task["reminder_sent_at"] = ""
    save_tasks(tasks)
    return best_task


def rename_task(query, new_title):
    tasks, best_task, best_score = find_best_task(query, include_done=True)
    cleaned_title = (new_title or "").strip(" .")
    if best_task is None or best_score < 0.45 or not cleaned_title:
        return None

    best_task["title"] = cleaned_title
    save_tasks(tasks)
    return best_task


def delete_task(query):
    tasks, best_task, best_score = find_best_task(query, include_done=True)
    if best_task is None or best_score < 0.45:
        return None

    remaining = [task for task in tasks if task.get("id") != best_task.get("id")]
    save_tasks(remaining)
    return best_task


def get_latest_task(include_done=False):
    tasks = load_tasks()
    filtered = []
    for task in tasks:
        if not include_done and task.get("status") == "done":
            continue
        filtered.append(task)
    filtered.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return filtered[0] if filtered else None


def rollover_recurring_task(task):
    recurrence = (task.get("recurrence") or "").strip().lower()
    due_at = _parse_iso_datetime(task.get("due_at"))
    if not recurrence or due_at is None:
        task["status"] = "done"
        task["completed_at"] = _now()
        return task

    if recurrence == "daily":
        next_due = due_at + timedelta(days=1)
    elif recurrence == "weekly":
        next_due = due_at + timedelta(days=7)
    elif recurrence == "monthly":
        next_due = due_at + timedelta(days=30)
    else:
        task["status"] = "done"
        task["completed_at"] = _now()
        return task

    task["due_at"] = next_due.isoformat(timespec="seconds")
    task["remind_at"] = (next_due - timedelta(minutes=15)).isoformat(timespec="seconds")
    task["reminder_sent_at"] = ""
    task["completed_at"] = _now()
    task["status"] = "open"
    task["due"] = _format_due_label(next_due, recurrence)
    return task


def list_tasks(status="open"):
    tasks = load_tasks()
    if status == "all":
        return tasks
    return [task for task in tasks if task.get("status") == status]


def _format_due_label(dt_value, recurrence=""):
    now = _now_dt()
    if dt_value.date() == now.date():
        prefix = "today"
    elif dt_value.date() == (now + timedelta(days=1)).date():
        prefix = "tomorrow"
    else:
        prefix = dt_value.strftime("%Y-%m-%d")

    label = f"{prefix} at {dt_value.strftime('%I:%M %p').lstrip('0').lower()}"
    if recurrence:
        return f"{label} ({recurrence})"
    return label


def list_today_tasks():
    today = _now_dt().date()
    tasks = []
    for task in load_tasks():
        if task.get("status") != "open":
            continue
        due_at = _parse_iso_datetime(task.get("due_at"))
        if due_at and due_at.date() == today:
            tasks.append(task)
    tasks.sort(key=lambda item: item.get("due_at", ""))
    return tasks


def list_overdue_tasks():
    now = _now_dt()
    tasks = []
    for task in load_tasks():
        if task.get("status") != "open":
            continue
        due_at = _parse_iso_datetime(task.get("due_at"))
        if due_at and due_at < now:
            tasks.append(task)
    tasks.sort(key=lambda item: item.get("due_at", ""))
    return tasks


def list_completed_tasks(limit=10):
    tasks = [task for task in load_tasks() if task.get("status") == "done"]
    tasks.sort(key=lambda item: item.get("completed_at", ""), reverse=True)
    return tasks[:limit]


def get_task_snapshot(limit=6):
    tasks = list_tasks(status="open")
    items = []
    for task in tasks[:limit]:
        due = f" (due: {task['due']})" if task.get("due") else ""
        items.append(f"Open task - {task.get('title', '')}{due}")
    return items


def get_due_reminders(now=None):
    current = now or _now_dt()
    reminders = []
    for task in load_tasks():
        if task.get("status") != "open":
            continue
        remind_at = task.get("remind_at")
        if not remind_at or task.get("reminder_sent_at"):
            continue
        try:
            remind_dt = datetime.fromisoformat(remind_at)
        except ValueError:
            continue
        if remind_dt <= current:
            reminders.append(task)
    reminders.sort(key=lambda item: item.get("remind_at", ""))
    return reminders


def mark_task_reminder_sent(task_id):
    tasks = load_tasks()
    updated = None
    for task in tasks:
        if task.get("id") == task_id:
            task["reminder_sent_at"] = _now()
            updated = task
            break
    if updated:
        save_tasks(tasks)
    return updated


def search_profile(query, limit=5):
    matches = []
    for item in get_profile_snapshot():
        if not is_relevant_match(query, item, strict=False):
            continue
        score, overlap, _ = score_match(query, item)
        matches.append((score, overlap, item))
    matches.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [item for _, _, item in matches[:limit]]


def search_tasks(query, limit=5):
    matches = []
    for item in get_task_snapshot(limit=50):
        if not is_relevant_match(query, item, strict=False):
            continue
        score, overlap, _ = score_match(query, item)
        matches.append((score, overlap, item))
    matches.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [item for _, _, item in matches[:limit]]


def load_summaries():
    ensure_assistant_storage()
    summaries = _load_json(SUMMARIES_FILE, [])
    return [item for item in summaries if isinstance(item, dict)]


def save_summaries(summaries):
    ensure_assistant_storage()
    _save_json(SUMMARIES_FILE, summaries)


def _read_recent_log_entries(limit=6):
    if not os.path.exists(LOG_FILE):
        return []

    entries = []
    with open(LOG_FILE, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except Exception:
                continue
    return entries[-limit:]


def update_conversation_summary():
    ensure_assistant_storage()
    entries = _read_recent_log_entries(limit=6)
    if len(entries) < 3:
        return None

    last_timestamp = entries[-1].get("timestamp", "")
    summaries = load_summaries()
    if summaries and summaries[-1].get("source_end_timestamp") == last_timestamp:
        return summaries[-1]

    topics = []
    for entry in entries:
        user_text = (entry.get("user") or "").strip()
        reply_text = (entry.get("reply") or "").strip()
        if user_text:
            topics.append(f"User asked: {user_text}")
        if reply_text:
            topics.append(f"FRIDAY replied: {reply_text[:180]}")

    summary_text = " | ".join(topics[:6])
    summary = {
        "created_at": _now(),
        "source_end_timestamp": last_timestamp,
        "text": summary_text[:1000],
    }
    summaries.append(summary)
    summaries = summaries[-20:]
    save_summaries(summaries)
    return summary


def get_recent_summaries(limit=3):
    summaries = load_summaries()
    items = []
    for item in summaries[-limit:]:
        text = item.get("text", "").strip()
        if text:
            items.append(f"Recent summary - {text}")
    return items


def load_session_memory():
    ensure_assistant_storage()
    items = _load_json(SESSION_MEMORY_FILE, [])
    return [item for item in items if isinstance(item, dict)]


def save_session_memory(items):
    ensure_assistant_storage()
    _save_json(SESSION_MEMORY_FILE, items[-30:])


def add_session_turn(user_text, reply_text, intent="general"):
    items = load_session_memory()
    items.append(
        {
            "timestamp": _now(),
            "intent": intent,
            "user": (user_text or "").strip(),
            "reply": (reply_text or "").strip(),
        }
    )
    save_session_memory(items)


def get_session_context(limit=6):
    items = load_session_memory()[-limit:]
    context = []
    for item in items:
        user_text = item.get("user", "").strip()
        reply_text = item.get("reply", "").strip()
        if user_text:
            context.append(f"Session memory - User: {user_text}")
        if reply_text:
            context.append(f"Session memory - FRIDAY: {reply_text[:180]}")
    return context


def load_feedback_memory():
    ensure_assistant_storage()
    items = _load_json(FEEDBACK_MEMORY_FILE, [])
    return [item for item in items if isinstance(item, dict)]


def save_feedback_memory(items):
    ensure_assistant_storage()
    _save_json(FEEDBACK_MEMORY_FILE, items[-60:])


def detect_feedback_correction(user_text):
    text = (user_text or "").strip()
    lowered = text.lower()
    correction_markers = (
        "that answer was wrong",
        "that was wrong",
        "you were wrong",
        "wrong answer",
        "no that's wrong",
        "no that is wrong",
        "that is incorrect",
        "that's incorrect",
        "you are incorrect",
        "not what i meant",
        "i meant ",
        "actually,",
        "actually ",
        "instead,",
        "instead ",
        "no, i meant",
        "no i meant",
        "use a shorter answer",
        "answer more briefly",
        "be more concise",
        "keep it shorter",
        "use a simpler answer",
        "explain it more simply",
        "be more professional",
        "be less flirty",
        "be more casual",
    )
    return any(marker in lowered for marker in correction_markers)


def _extract_correction_text(user_text):
    text = (user_text or "").strip()
    patterns = [
        r"(?:i meant|actually|instead)\s*:?\s*(.+)$",
        r"(?:no,\s*i meant|no\s+i meant)\s*:?\s*(.+)$",
        r"(?:that answer was wrong|that was wrong|you were wrong|wrong answer)\s*[,.:-]?\s*(.+)$",
        r"(?:not what i meant)\s*[,.:-]?\s*(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip(" .")
    return ""


def classify_feedback(user_text):
    lowered = (user_text or "").strip().lower()
    style_rules = [
        (("use a shorter answer", "answer more briefly", "be more concise", "keep it shorter"), "brevity", "shorter answers"),
        (("use a simpler answer", "explain it more simply", "simpler explanation"), "clarity", "simpler explanations"),
        (("be more professional", "sound more professional"), "tone", "professional tone"),
        (("be less flirty", "less flirty"), "tone", "less flirty tone"),
        (("be more casual", "sound more casual"), "tone", "casual tone"),
    ]
    for markers, category, preference_value in style_rules:
        if any(marker in lowered for marker in markers):
            return {
                "feedback_type": "style",
                "style_category": category,
                "preference_value": preference_value,
            }
    return {
        "feedback_type": "factual",
        "style_category": "",
        "preference_value": "",
    }


def record_feedback_correction(user_text):
    if not detect_feedback_correction(user_text):
        return None

    classification = classify_feedback(user_text)
    session_items = load_session_memory()
    previous_turn = session_items[-1] if session_items else {}
    previous_user = (previous_turn.get("user") or "").strip()
    previous_reply = (previous_turn.get("reply") or "").strip()
    correction_text = _extract_correction_text(user_text)

    if classification["feedback_type"] == "factual" and not previous_user and not previous_reply:
        return None

    if classification["feedback_type"] == "style" and classification["preference_value"]:
        set_preference(f"response style {classification['style_category']}", classification["preference_value"])

    entry = {
        "id": uuid.uuid4().hex[:10],
        "timestamp": _now(),
        "feedback_user_text": (user_text or "").strip(),
        "correction": correction_text,
        "feedback_type": classification["feedback_type"],
        "style_category": classification["style_category"],
        "preference_value": classification["preference_value"],
        "previous_user": previous_user,
        "previous_reply": previous_reply[:500],
    }
    items = load_feedback_memory()
    duplicate = any(
        item.get("previous_user", "") == entry["previous_user"]
        and item.get("previous_reply", "") == entry["previous_reply"]
        and item.get("feedback_user_text", "") == entry["feedback_user_text"]
        for item in items
    )
    if not duplicate:
        items.append(entry)
        save_feedback_memory(items)
    return entry


def get_feedback_context(query, limit=4):
    matches = []
    style_context = []
    for item in load_feedback_memory():
        previous_user = item.get("previous_user", "")
        previous_reply = item.get("previous_reply", "")
        correction = item.get("correction", "")
        feedback_text = item.get("feedback_user_text", "")
        feedback_type = item.get("feedback_type", "factual")
        if feedback_type == "style":
            preference_value = item.get("preference_value", "")
            style_category = item.get("style_category", "")
            if preference_value:
                style_context.append(
                    f"Feedback memory - Style preference: prefer {preference_value}"
                    + (f" for {style_category}" if style_category else "")
                )
            continue
        combined = " | ".join(part for part in (previous_user, previous_reply, correction, feedback_text) if part)
        if not combined or not is_relevant_match(query, combined, strict=False):
            continue
        score, overlap, _ = score_match(query, combined)
        matches.append((score, overlap, item))
    matches.sort(key=lambda row: (row[0], row[1]), reverse=True)

    context = []
    for _, _, item in matches[:limit]:
        previous_user = item.get("previous_user", "")
        previous_reply = item.get("previous_reply", "")
        correction = item.get("correction", "")
        feedback_text = item.get("feedback_user_text", "")
        parts = [
            f"Feedback memory - Previous user request: {previous_user}" if previous_user else "",
            f"Feedback memory - Previous FRIDAY reply: {previous_reply}" if previous_reply else "",
            f"Feedback memory - User correction: {correction or feedback_text}",
        ]
        context.append("\n".join(part for part in parts if part))
    combined_context = []
    seen = set()
    for item in style_context + context:
        if item and item not in seen:
            combined_context.append(item)
            seen.add(item)
    return combined_context[:limit + 3]


def extract_important_memory(user_text, reply_text=""):
    text = f"{user_text}\n{reply_text}".strip()
    lowered = text.lower()
    stored = []

    patterns = [
        (r"\bi go to gym at ([^\n.]+)", "gym schedule"),
        (r"\bi study ([^\n.]+)", "study"),
        (r"\bi prefer ([^\n.]+)", "preference"),
        (r"\bmy goal is ([^\n.]+)", "goal"),
        (r"\bi use ([^\n.]+)", "tool"),
        (r"\bi work on ([^\n.]+)", "project"),
    ]

    for pattern, label in patterns:
        match = re.search(pattern, lowered, re.IGNORECASE)
        if not match:
            continue
        value = match.group(1).strip(" .")
        if label == "preference":
            set_preference("preference", value)
            stored.append(f"Preference - preference: {value}")
        elif label == "gym schedule":
            set_preference("gym schedule", value)
            stored.append(f"Preference - gym schedule: {value}")
            add_life_thread_entry("gym_progress", f"Gym schedule: {value}")
        elif label == "tool":
            set_preference("tools", value)
            stored.append(f"Preference - tools: {value}")
        elif label == "study":
            fact = f"User study focus: {value}"
            if add_fact(fact):
                stored.append(f"Fact - {fact}")
            add_life_thread_entry("studies", value)
        elif label == "project":
            fact = f"User project: {value}"
            if add_fact(fact):
                stored.append(f"Fact - {fact}")
            add_life_thread_entry("projects", value)
        else:
            fact = f"User {label}: {value}"
            if add_fact(fact):
                stored.append(f"Fact - {fact}")

    return stored


def load_life_threads():
    ensure_assistant_storage()
    data = _load_json(LIFE_THREADS_FILE, {"gym_progress": [], "studies": [], "projects": [], "goals": []})
    for key in ("gym_progress", "studies", "projects", "goals"):
        data.setdefault(key, [])
    return data


def save_life_threads(data):
    ensure_assistant_storage()
    _save_json(LIFE_THREADS_FILE, data)


def add_life_thread_entry(thread_name, text):
    cleaned = (text or "").strip()
    if not cleaned:
        return
    data = load_life_threads()
    items = data.setdefault(thread_name, [])
    entry = {"text": cleaned, "timestamp": _now()}
    if not any(item.get("text", "").lower() == cleaned.lower() for item in items if isinstance(item, dict)):
        items.append(entry)
    data[thread_name] = items[-20:]
    save_life_threads(data)


def get_life_thread_snapshot(limit=2):
    data = load_life_threads()
    lines = []
    for key, label in (("gym_progress", "Gym"), ("studies", "Study"), ("projects", "Project"), ("goals", "Goal")):
        for item in data.get(key, [])[-limit:]:
            if isinstance(item, dict) and item.get("text"):
                lines.append(f"{label} thread - {item['text']}")
    return lines


def save_goal_roadmap(goal, roadmap_text):
    cleaned_goal = (goal or "").strip()
    cleaned_text = (roadmap_text or "").strip()
    if not cleaned_goal or not cleaned_text:
        return
    add_life_thread_entry("goals", f"{cleaned_goal}: {cleaned_text[:600]}")


def recall_similar_memory(query, limit=3):
    candidates = get_profile_snapshot() + get_recent_summaries(limit=4) + get_session_context(limit=8) + get_life_thread_snapshot(limit=4)
    matches = []
    for item in candidates:
        if not is_relevant_match(query, item, strict=False):
            continue
        score, overlap, _ = score_match(query, item)
        matches.append((score, overlap, item))
    matches.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [item for _, _, item in matches[:limit]]

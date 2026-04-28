import json
import os
import re
import time
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROUTINES_FILE = os.path.join(BASE_DIR, "friday_routines.json")
ROUTINE_SCHEDULES_FILE = os.path.join(BASE_DIR, "friday_routine_schedules.json")

DEFAULT_ROUTINES = {
    "focus mode": [
        "open vscode",
        "open powershell",
        "volume down",
    ],
    "study mode": [
        "open chrome",
        "open d drive",
        "volume down",
    ],
    "movie mode": [
        "volume up",
        "mute youtube",
        "fullscreen youtube",
    ],
}


def ensure_routine_storage():
    if not os.path.exists(ROUTINES_FILE):
        with open(ROUTINES_FILE, "w", encoding="utf-8") as handle:
            json.dump(DEFAULT_ROUTINES, handle, ensure_ascii=False, indent=2)
    if not os.path.exists(ROUTINE_SCHEDULES_FILE):
        with open(ROUTINE_SCHEDULES_FILE, "w", encoding="utf-8") as handle:
            json.dump([], handle, ensure_ascii=False, indent=2)


def _load_routines():
    ensure_routine_storage()
    try:
        with open(ROUTINES_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return dict(DEFAULT_ROUTINES)


def _save_routines(data):
    with open(ROUTINES_FILE, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def _load_schedules():
    ensure_routine_storage()
    try:
        with open(ROUTINE_SCHEDULES_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _save_schedules(data):
    with open(ROUTINE_SCHEDULES_FILE, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def can_handle_routine_command(text):
    normalized = normalize(text)
    triggers = (
        "create routine",
        "save routine",
        "remember routine",
        "run routine",
        "start routine",
        "launch routine",
        "show routines",
        "list routines",
        "delete routine",
        "remove routine",
        "show routine",
        "schedule routine",
        "unschedule routine",
        "show routine schedules",
        "list routine schedules",
    )
    return any(trigger in normalized for trigger in triggers)


def handle_routine_command(command, executor):
    normalized = normalize(command)

    if normalized in {"list routines", "show routines"}:
        return list_routines()

    if normalized in {"show routine schedules", "list routine schedules"}:
        return list_schedules()

    save_match = re.search(r"(?:create|save|remember)\s+routine\s+(.+?)\s*:\s*(.+)$", command, flags=re.IGNORECASE)
    if save_match:
        name = clean_name(save_match.group(1))
        steps = parse_steps(save_match.group(2))
        if not name or not steps:
            return "Tell me the routine name and steps, like `create routine focus mode: open vscode, open chrome`."
        return save_routine(name, steps)

    schedule_match = re.search(r"(?:schedule)\s+routine\s+(.+?)\s+(every.+)$", command, flags=re.IGNORECASE)
    if schedule_match:
        name = clean_name(schedule_match.group(1))
        schedule_text = schedule_match.group(2).strip()
        return save_schedule(name, schedule_text)

    run_match = re.search(r"(?:run|start|launch)\s+routine\s+(.+)$", command, flags=re.IGNORECASE)
    if run_match:
        name = clean_name(run_match.group(1))
        if not name:
            return "Tell me which routine to run."
        return run_routine(name, executor)

    show_match = re.search(r"show\s+routine\s+(.+)$", command, flags=re.IGNORECASE)
    if show_match:
        name = clean_name(show_match.group(1))
        return show_routine(name)

    delete_match = re.search(r"(?:delete|remove)\s+routine\s+(.+)$", command, flags=re.IGNORECASE)
    if delete_match:
        name = clean_name(delete_match.group(1))
        return delete_routine(name)

    unschedule_match = re.search(r"(?:unschedule)\s+routine\s+(.+)$", command, flags=re.IGNORECASE)
    if unschedule_match:
        name = clean_name(unschedule_match.group(1))
        return delete_schedule(name)

    return None


def parse_steps(text):
    cleaned = (text or "").strip()
    if not cleaned:
        return []

    parts = re.split(r"\s*(?:,| then | and then | \| )\s*", cleaned, flags=re.IGNORECASE)
    steps = [part.strip(" .") for part in parts if part.strip(" .")]
    return steps[:12]


def save_routine(name, steps):
    routines = _load_routines()
    routines[name] = steps
    _save_routines(routines)
    return f"Saved routine `{name}` with {len(steps)} steps."


def run_routine(name, executor):
    routines = _load_routines()
    steps = routines.get(name)
    if not steps:
        similar = ", ".join(sorted(routines.keys())[:4])
        if similar:
            return f"I couldn't find routine `{name}`. Available routines: {similar}"
        return f"I couldn't find routine `{name}`."

    results = [f"Running routine `{name}`..."]
    for index, step in enumerate(steps, start=1):
        result = executor(step)
        if isinstance(result, dict):
            message = result.get("message", "This step needs confirmation.")
            results.append(f"{index}. {step} -> {message}")
            results.append("Routine paused because one step needs confirmation.")
            break
        results.append(f"{index}. {step} -> {result or 'Done.'}")
        time.sleep(0.35)

    return "\n".join(results)


def list_routines():
    routines = _load_routines()
    if not routines:
        return "No routines saved yet."

    lines = ["Mission routines ready:"]
    for name in sorted(routines):
        lines.append(f"- {name}: {', '.join(routines[name][:4])}")
    return "\n".join(lines)


def get_routine_names(limit=4):
    return sorted(_load_routines().keys())[:limit]


def show_routine(name):
    routines = _load_routines()
    steps = routines.get(name)
    if not steps:
        return f"I couldn't find routine `{name}`."
    return "Routine `" + name + "`:\n" + "\n".join(f"{index}. {step}" for index, step in enumerate(steps, start=1))


def delete_routine(name):
    routines = _load_routines()
    if name not in routines:
        return f"I couldn't find routine `{name}`."
    del routines[name]
    _save_routines(routines)
    delete_schedule(name)
    return f"Deleted routine `{name}`."


def save_schedule(name, schedule_text):
    routines = _load_routines()
    if name not in routines:
        return f"I couldn't find routine `{name}`."

    schedule = parse_schedule_text(schedule_text)
    if not schedule:
        return "Try a schedule like `schedule routine focus mode every morning` or `schedule routine focus mode every day at 9 am`."

    schedules = [item for item in _load_schedules() if item.get("routine") != name]
    schedule["routine"] = name
    schedule["last_run_key"] = ""
    schedules.append(schedule)
    _save_schedules(schedules)
    return f"Scheduled routine `{name}` for {schedule['label']}."


def delete_schedule(name):
    schedules = _load_schedules()
    remaining = [item for item in schedules if item.get("routine") != name]
    if len(remaining) == len(schedules):
        return f"I couldn't find a saved schedule for routine `{name}`."
    _save_schedules(remaining)
    return f"Removed the schedule for routine `{name}`."


def list_schedules():
    schedules = _load_schedules()
    if not schedules:
        return "No routine schedules saved yet."

    lines = ["Routine schedules:"]
    for item in schedules:
        lines.append(f"- {item.get('routine', '')}: {item.get('label', '')}")
    return "\n".join(lines)


def parse_schedule_text(text):
    normalized = normalize(text)
    if not normalized.startswith("every"):
        return None

    hour = 9
    minute = 0
    label = normalized

    if "morning" in normalized:
        hour, minute = 9, 0
    elif "afternoon" in normalized:
        hour, minute = 15, 0
    elif "evening" in normalized:
        hour, minute = 19, 0
    elif "night" in normalized:
        hour, minute = 21, 0

    time_match = re.search(r"at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", normalized)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or 0)
        meridiem = (time_match.group(3) or "").lower()
        if meridiem == "pm" and hour != 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0

    schedule_type = "daily"
    weekdays = []
    if "weekday" in normalized:
        schedule_type = "weekday"
        weekdays = [0, 1, 2, 3, 4]
    elif "weekend" in normalized:
        schedule_type = "weekend"
        weekdays = [5, 6]

    return {
        "type": schedule_type,
        "weekdays": weekdays,
        "hour": hour,
        "minute": minute,
        "label": label,
    }


def get_due_scheduled_routines(now=None):
    current = now or datetime.now()
    due = []
    schedules = _load_schedules()

    for item in schedules:
        if not is_schedule_due(item, current):
            continue
        due.append(item)

    return due


def is_schedule_due(schedule, current):
    schedule_type = schedule.get("type", "daily")
    if schedule_type == "weekday" and current.weekday() not in schedule.get("weekdays", [0, 1, 2, 3, 4]):
        return False
    if schedule_type == "weekend" and current.weekday() not in schedule.get("weekdays", [5, 6]):
        return False

    if current.hour != int(schedule.get("hour", 9)) or current.minute != int(schedule.get("minute", 0)):
        return False

    run_key = current.strftime("%Y-%m-%d %H:%M")
    return schedule.get("last_run_key") != run_key


def mark_schedule_ran(routine_name, now=None):
    current = now or datetime.now()
    run_key = current.strftime("%Y-%m-%d %H:%M")
    schedules = _load_schedules()
    changed = False
    for item in schedules:
        if item.get("routine") == routine_name:
            item["last_run_key"] = run_key
            changed = True
    if changed:
        _save_schedules(schedules)


def clean_name(text):
    cleaned = re.sub(r"\s+", " ", (text or "").strip().lower()).strip(" .")
    return cleaned


def normalize(text):
    return re.sub(r"\s+", " ", (text or "").strip().lower())

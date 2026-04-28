import ctypes
import json
import os
from datetime import datetime

from assistant_memory import get_life_thread_snapshot, load_profile
from personality_engine import apply_personality
from screen_vision import latest_screen_snapshot


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRESENCE_STATE_FILE = os.path.join(BASE_DIR, "presence_state.json")


def _load_state():
    try:
        with open(PRESENCE_STATE_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"last_prompts": {}}


def _save_state(state):
    with open(PRESENCE_STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2)


def get_presence_prompt():
    now = datetime.now()
    profile = load_profile()
    life_threads = get_life_thread_snapshot(limit=3)
    active_window = get_active_window_title()
    screen = latest_screen_snapshot() or {}
    state = _load_state()

    prompt = maybe_gym_prompt(now, profile, life_threads, state)
    if prompt:
        return prompt

    prompt = maybe_coding_prompt(active_window, state)
    if prompt:
        return prompt

    prompt = maybe_project_prompt(active_window, profile, life_threads, state)
    if prompt:
        return prompt

    prompt = maybe_error_prompt(screen, state)
    if prompt:
        return prompt

    prompt = maybe_youtube_prompt(active_window, screen, state)
    if prompt:
        return prompt

    prompt = maybe_late_night_prompt(now, state)
    if prompt:
        return prompt

    return ""


def maybe_gym_prompt(now, profile, life_threads, state):
    gym_schedule = get_preference(profile, "gym schedule")
    if not gym_schedule:
        return ""

    if "6" not in gym_schedule.lower():
        return ""

    if now.hour == 17 and 45 <= now.minute <= 59 and allow_prompt("gym", state, cooldown_minutes=90):
        text = "It's almost 6... gym time, right? Don't tell me you're skipping again."
        if any("Gym thread" in item for item in life_threads):
            text = "It's almost 6... gym time again. You do remember what you told me, right?"
        return finalize_prompt("gym", text, state)
    return ""


def maybe_coding_prompt(active_window, state):
    lowered = active_window.lower()
    if any(name in lowered for name in ("visual studio code", "vscode", "pycharm", "cursor")):
        if allow_prompt("coding", state, cooldown_minutes=60):
            return finalize_prompt("coding", "Back to coding... want help or are you focusing right now?", state)
    return ""


def maybe_project_prompt(active_window, profile, life_threads, state):
    lowered = active_window.lower()
    project = get_fact_or_pref(profile, "project")
    study = get_fact_or_pref(profile, "study")

    if project and any(name in lowered for name in ("visual studio code", "vscode", "cursor")):
        if allow_prompt("project", state, cooldown_minutes=120):
            if any("Project thread" in item for item in life_threads):
                return finalize_prompt("project", "How's your project going? You were onto something interesting last time too.", state)
            return finalize_prompt("project", "How's your project going? You were working on something interesting.", state)

    if study and any(name in lowered for name in ("chrome", "edge", "browser", "pdf")):
        if allow_prompt("study", state, cooldown_minutes=150):
            if any("Study thread" in item for item in life_threads):
                return finalize_prompt("study", "Study mode again? You always act calm first and panic later.", state)
            return finalize_prompt("study", "Study mode again? Try not to get distracted this time.", state)
    return ""


def maybe_error_prompt(screen, state):
    summary = (screen.get("summary") or "").lower()
    if any(word in summary for word in ("error", "traceback", "exception", "failed")):
        if allow_prompt("error", state, cooldown_minutes=45):
            return finalize_prompt("error", "That error again... want me to help fix it?", state)
    return ""


def maybe_youtube_prompt(active_window, screen, state):
    lowered = active_window.lower()
    summary = (screen.get("summary") or "").lower()
    if "youtube" in lowered or "youtube" in summary:
        if allow_prompt("youtube", state, cooldown_minutes=75):
            return finalize_prompt("youtube", "Hmm... break time or procrastination? Be honest.", state)
    return ""


def maybe_late_night_prompt(now, state):
    if now.hour >= 23 and allow_prompt("sleep", state, cooldown_minutes=180):
        return finalize_prompt("sleep", "Still awake... you should sleep soon, you know.", state)
    return ""


def finalize_prompt(key, text, state):
    state.setdefault("last_prompts", {})[key] = datetime.now().isoformat(timespec="seconds")
    _save_state(state)
    return apply_personality(text, text)


def allow_prompt(key, state, cooldown_minutes=60):
    last = state.get("last_prompts", {}).get(key, "")
    if not last:
        return True
    try:
        last_dt = datetime.fromisoformat(last)
    except ValueError:
        return True
    delta = (datetime.now() - last_dt).total_seconds() / 60
    return delta >= cooldown_minutes


def get_preference(profile, key_name):
    preferences = profile.get("preferences", {})
    item = preferences.get(key_name)
    if isinstance(item, dict):
        return item.get("value", "")
    return ""


def get_fact_or_pref(profile, hint):
    for key, value in profile.get("preferences", {}).items():
        if hint in key.lower():
            if isinstance(value, dict):
                return value.get("value", "")
    for fact in profile.get("facts", []):
        text = fact.get("text", "") if isinstance(fact, dict) else ""
        if hint in text.lower():
            return text
    return ""


def get_active_window_title():
    if os.name != "nt":
        return ""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value or ""
    except Exception:
        return ""


def get_idle_seconds():
    if os.name != "nt":
        return 0

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if user32.GetLastInputInfo(ctypes.byref(info)):
            millis = kernel32.GetTickCount() - info.dwTime
            return millis / 1000.0
    except Exception:
        pass
    return 0

import json
import os

from control_profile import profile_to_label


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEBUG_FILE = os.path.join(BASE_DIR, "brain", "debug_snapshot.json")


def ensure_debug_storage():
    os.makedirs(os.path.dirname(DEBUG_FILE), exist_ok=True)
    if not os.path.exists(DEBUG_FILE):
        with open(DEBUG_FILE, "w", encoding="utf-8") as handle:
            json.dump({}, handle, ensure_ascii=False, indent=2)


def write_debug_snapshot(payload):
    ensure_debug_storage()
    with open(DEBUG_FILE, "w", encoding="utf-8") as handle:
        json.dump(payload or {}, handle, ensure_ascii=False, indent=2)


def read_debug_snapshot():
    ensure_debug_storage()
    try:
        with open(DEBUG_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def format_debug_snapshot(payload):
    data = payload or {}
    lines = ["COGNITIVE DEBUG"]
    for key in ("mode", "complexity", "response_type", "confidence", "finalizer_decision"):
        value = data.get(key, "")
        if key == "mode" and isinstance(value, dict):
            value = profile_to_label(value)
        if value != "":
            lines.append(f"{key}: {value}")
    for key in ("draft_a", "draft_b", "critic", "final_answer"):
        value = (data.get(key) or "").strip()
        if value:
            lines.append("")
            lines.append(f"{key}:")
            lines.append(value[:700])
    return "\n".join(lines)

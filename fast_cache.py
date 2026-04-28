import json
import os
from datetime import datetime

from control_profile import normalize_control_mode


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FAST_CACHE_FILE = os.path.join(BASE_DIR, "brain", "fast_cache.json")


def _now():
    return datetime.now().isoformat(timespec="seconds")


def ensure_fast_cache_storage():
    os.makedirs(os.path.dirname(FAST_CACHE_FILE), exist_ok=True)
    if not os.path.exists(FAST_CACHE_FILE):
        with open(FAST_CACHE_FILE, "w", encoding="utf-8") as handle:
            json.dump({"items": []}, handle, ensure_ascii=False, indent=2)


def _load():
    ensure_fast_cache_storage()
    try:
        with open(FAST_CACHE_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            data.setdefault("items", [])
            return data
    except Exception:
        pass
    return {"items": []}


def _save(data):
    ensure_fast_cache_storage()
    with open(FAST_CACHE_FILE, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def _key(user_input, control_mode=None):
    profile = normalize_control_mode(control_mode)
    return {
        "query": (user_input or "").strip().lower(),
        "depth_mode": profile["depth_mode"],
        "response_style": profile["response_style"],
        "safe_mode": bool(profile["safe_mode"]),
    }


def get_cached_response(user_input, control_mode=None):
    target = _key(user_input, control_mode)
    for item in reversed(_load().get("items", [])):
        if all(item.get(k) == v for k, v in target.items()):
            return (item.get("answer") or "").strip()
    return ""


def put_cached_response(user_input, answer_text, control_mode=None):
    clean_answer = (answer_text or "").strip()
    if not clean_answer:
        return None
    data = _load()
    items = [item for item in data.get("items", []) if not all(item.get(k) == v for k, v in _key(user_input, control_mode).items())]
    entry = _key(user_input, control_mode)
    entry.update({"answer": clean_answer, "updated_at": _now()})
    items.append(entry)
    data["items"] = items[-10:]
    _save(data)
    return entry

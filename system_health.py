import json
import os
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HEALTH_FILE = os.path.join(BASE_DIR, "brain", "system_health.json")


def _now():
    return datetime.now().isoformat(timespec="seconds")


def ensure_health_storage():
    os.makedirs(os.path.dirname(HEALTH_FILE), exist_ok=True)
    if not os.path.exists(HEALTH_FILE):
        with open(HEALTH_FILE, "w", encoding="utf-8") as handle:
            json.dump({"events": []}, handle, ensure_ascii=False, indent=2)


def _load():
    ensure_health_storage()
    try:
        with open(HEALTH_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            data.setdefault("events", [])
            return data
    except Exception:
        pass
    return {"events": []}


def _save(data):
    ensure_health_storage()
    with open(HEALTH_FILE, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def record_health_event(component, latency_ms=0, ok=True, note=""):
    data = _load()
    events = data.get("events", [])
    events.append(
        {
            "created_at": _now(),
            "component": (component or "unknown").strip(),
            "latency_ms": int(latency_ms or 0),
            "ok": bool(ok),
            "note": (note or "").strip(),
        }
    )
    data["events"] = events[-40:]
    _save(data)


def get_health_summary():
    events = _load().get("events", [])
    if not events:
        return {"healthy": True, "average_latency_ms": 0, "failure_rate": 0.0}
    average_latency = sum(int(item.get("latency_ms") or 0) for item in events) / len(events)
    failures = sum(1 for item in events if not item.get("ok", False))
    return {
        "healthy": average_latency < 5000 and failures / len(events) < 0.35,
        "average_latency_ms": average_latency,
        "failure_rate": failures / len(events),
    }


def should_force_safe_mode():
    summary = get_health_summary()
    return (not summary["healthy"]) or summary["average_latency_ms"] > 6500 or summary["failure_rate"] > 0.4

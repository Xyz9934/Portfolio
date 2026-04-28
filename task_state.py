import json
import os
import uuid
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TASK_STATE_FILE = os.path.join(BASE_DIR, "task_state.json")


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _load():
    try:
        with open(TASK_STATE_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"current_task": None, "history": []}


def _save(data):
    with open(TASK_STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def start_task(user_input, intent, steps):
    data = _load()
    task = {
        "task_id": uuid.uuid4().hex[:10],
        "user_input": user_input,
        "intent": intent,
        "steps": [{"title": step, "status": "pending"} for step in steps],
        "current_step": 0,
        "status": "running",
        "result": "",
        "started_at": _now(),
        "updated_at": _now(),
        "completed_at": "",
    }
    data["current_task"] = task
    _save(data)
    return task


def advance_step(note=""):
    data = _load()
    task = data.get("current_task")
    if not task:
        return None

    steps = task.get("steps", [])
    index = int(task.get("current_step", 0))
    if 0 <= index < len(steps):
        steps[index]["status"] = "done"
        if note:
            steps[index]["note"] = note
        task["current_step"] = min(index + 1, len(steps))

    if task["current_step"] < len(steps):
        steps[task["current_step"]]["status"] = "in_progress"

    task["updated_at"] = _now()
    _save(data)
    return task


def finish_task(result):
    data = _load()
    task = data.get("current_task")
    if not task:
        return None

    for step in task.get("steps", []):
        if step.get("status") in {"pending", "in_progress"}:
            step["status"] = "done"
    task["status"] = "completed"
    task["result"] = result
    task["updated_at"] = _now()
    task["completed_at"] = _now()
    data.setdefault("history", []).append(task)
    data["history"] = data["history"][-25:]
    data["current_task"] = None
    _save(data)
    return task


def fail_task(error_message):
    data = _load()
    task = data.get("current_task")
    if not task:
        return None

    task["status"] = "failed"
    task["result"] = error_message
    task["updated_at"] = _now()
    task["completed_at"] = _now()
    data.setdefault("history", []).append(task)
    data["history"] = data["history"][-25:]
    data["current_task"] = None
    _save(data)
    return task


def get_current_task():
    return _load().get("current_task")


def get_last_task():
    history = _load().get("history", [])
    return history[-1] if history else None


def format_last_plan_for_user(user_input):
    task = get_last_task()
    if not task or task.get("user_input") != user_input:
        return ""

    lines = [f"Planner [{task.get('intent', 'general')}]"]
    for index, step in enumerate(task.get("steps", []), start=1):
        status = step.get("status", "pending")
        lines.append(f"{index}. {step.get('title', '')} [{status}]")
    return "\n".join(lines)


def format_task_for_user(task):
    if not task:
        return ""
    lines = [f"Planner [{task.get('intent', 'general')}]"]
    for index, step in enumerate(task.get("steps", []), start=1):
        status = step.get("status", "pending")
        lines.append(f"{index}. {step.get('title', '')} [{status}]")
    return "\n".join(lines)

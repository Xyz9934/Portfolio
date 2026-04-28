import json
import os
import time
from datetime import datetime

from control_profile import normalize_control_mode


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BUDGET_FILE = os.path.join(BASE_DIR, "brain", "execution_budget.json")


def _now():
    return datetime.now().isoformat(timespec="seconds")


def ensure_execution_budget_storage():
    os.makedirs(os.path.dirname(BUDGET_FILE), exist_ok=True)
    if not os.path.exists(BUDGET_FILE):
        with open(BUDGET_FILE, "w", encoding="utf-8") as handle:
            json.dump({"last_budget": {}}, handle, ensure_ascii=False, indent=2)


def build_execution_budget(control_mode=None, priority_level="medium"):
    profile = normalize_control_mode(control_mode)
    depth = profile["depth_mode"]
    budget = {
        "created_at": _now(),
        "depth_mode": depth,
        "priority_level": priority_level,
        "max_time_ms": 7000,
        "max_model_calls": 3,
        "max_memory_fetch": 5,
        "allow_simulation": True,
        "allow_critic": True,
        "allow_deep_memory": True,
        "start_time": time.perf_counter(),
    }

    if depth == "quick" or profile["force_fast"]:
        budget.update({"max_time_ms": 2800, "max_model_calls": 1, "max_memory_fetch": 2, "allow_simulation": False, "allow_critic": False, "allow_deep_memory": False})
    elif depth == "smart":
        budget.update({"max_time_ms": 5200, "max_model_calls": 2, "max_memory_fetch": 4, "allow_simulation": False})
    elif depth == "deep":
        budget.update({"max_time_ms": 9000, "max_model_calls": 4, "max_memory_fetch": 5, "allow_simulation": True, "allow_critic": True, "allow_deep_memory": True})
    elif depth == "safe":
        budget.update({"max_time_ms": 2200, "max_model_calls": 1, "max_memory_fetch": 1, "allow_simulation": False, "allow_critic": False, "allow_deep_memory": False})

    if profile.get("full_research"):
        budget.update({"max_time_ms": 14000, "max_model_calls": 5, "max_memory_fetch": 8, "allow_simulation": True, "allow_critic": True, "allow_deep_memory": True})

    if profile["safe_mode"]:
        budget.update({"max_time_ms": min(budget["max_time_ms"], 2200), "max_model_calls": 1, "max_memory_fetch": 1, "allow_simulation": False, "allow_critic": False, "allow_deep_memory": False})
    if priority_level == "low":
        budget["max_time_ms"] = min(budget["max_time_ms"], 4000)
    save_budget_snapshot(budget)
    return budget


def elapsed_ms(budget):
    return int((time.perf_counter() - float(budget.get("start_time") or time.perf_counter())) * 1000)


def budget_exceeded(budget):
    return elapsed_ms(budget) > int(budget.get("max_time_ms") or 0)


def can_use_stage(budget, stage_name):
    if budget_exceeded(budget):
        return False
    if stage_name == "simulation":
        return bool(budget.get("allow_simulation", False))
    if stage_name == "critic":
        return bool(budget.get("allow_critic", False))
    if stage_name == "deep_memory":
        return bool(budget.get("allow_deep_memory", False))
    return True


def save_budget_snapshot(budget):
    ensure_execution_budget_storage()
    snapshot = dict(budget)
    snapshot["start_time"] = 0
    with open(BUDGET_FILE, "w", encoding="utf-8") as handle:
        json.dump({"last_budget": snapshot}, handle, ensure_ascii=False, indent=2)

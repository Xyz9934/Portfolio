from brain_architecture import (
    build_plan,
    detect_intent,
    refine_response,
    run_10_layer_brain,
    select_agent,
)
from task_state import format_task_for_user


_PLANNER_CALLBACK = None


def set_planner_callback(callback):
    global _PLANNER_CALLBACK
    _PLANNER_CALLBACK = callback


def emit_plan_update(task):
    if _PLANNER_CALLBACK:
        try:
            _PLANNER_CALLBACK(format_task_for_user(task))
        except Exception:
            pass


def run_friday_request(user_input, answer_mode="auto"):
    return run_10_layer_brain(user_input, planner_callback=_PLANNER_CALLBACK, answer_mode=answer_mode)

from brain_runtime import set_pending_pc_command
from execution_feedback import log_execution_feedback
from routine_brain import can_handle_routine_command, handle_routine_command
from semantic_brain import learn_text
from storage_status import get_storage_status, is_storage_status_command
from screen_vision import can_handle_screen_command
from tool_registry import run_tool


def as_system_reply(message):
    return {"message": message, "response_style": "system"}


def handle_automation_task(user_input, task=None):
    normalized = (user_input or "").strip()

    if is_storage_status_command(normalized):
        message = get_storage_status()
        log_execution_feedback("storage_status", message, success=True)
        return as_system_reply(message)

    if can_handle_routine_command(normalized):
        message = handle_routine_command(normalized, lambda step: run_tool("pc_control", step))
        log_execution_feedback("routine_command", message, success="couldn't" not in message.lower())
        return as_system_reply(message)

    if normalized.lower().startswith("learn:"):
        message = learn_text(normalized[6:].strip())
        log_execution_feedback("learn_text", message, success=True)
        return as_system_reply(message)

    if can_handle_screen_command(user_input):
        message = run_tool("screen_reader", user_input)
        log_execution_feedback("screen_reader", str(message), success=bool(message))
        return as_system_reply(message)

    result = run_tool("pc_control", user_input)
    if isinstance(result, dict):
        if result.get("needs_confirmation"):
            set_pending_pc_command(result.get("command", ""))
        message = result.get("message", "Automation needs confirmation.")
        log_execution_feedback("pc_control", message, success=not result.get("needs_confirmation"))
        return as_system_reply(message)
    if result:
        log_execution_feedback("pc_control", str(result), success=True)
        return as_system_reply(result)
    log_execution_feedback("pc_control", "I couldn't execute the automation request yet.", success=False)
    return as_system_reply("I understood this as an automation request, but I couldn't execute it yet.")

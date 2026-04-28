from assistant_brain import handle_assistant_command
from assistant_memory import get_profile_snapshot, get_recent_summaries, get_session_context, get_task_snapshot


def handle_memory_task(user_input, task=None):
    direct = handle_assistant_command(user_input)
    if direct:
        return direct

    memory_items = get_profile_snapshot() + get_task_snapshot(limit=6) + get_recent_summaries(limit=2) + get_session_context(limit=4)
    if not memory_items:
        return "I don't have enough memory saved yet."
    return "Memory snapshot:\n- " + "\n- ".join(memory_items[:12])

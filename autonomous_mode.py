from agent_pipeline import run_agent_pipeline


def should_use_autonomous_mode(user_text):
    lowered = (user_text or "").lower()
    triggers = (
        "agent mode",
        "autonomous",
        "do this for me",
        "handle this end to end",
        "figure it out step by step",
        "plan and execute",
    )
    return any(trigger in lowered for trigger in triggers)


def run_autonomous_pipeline(user_text, private_context=None, life_context=None, memory_context=None):
    return run_agent_pipeline(
        user_text,
        private_context=private_context,
        life_context=life_context,
        memory_context=memory_context,
    )

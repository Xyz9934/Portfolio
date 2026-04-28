from assistant_memory import get_session_context
from identity_model import refresh_user_identity
from initiative_engine import generate_initiative_from_context
from knowledge_expansion import update_knowledge_tasks_from_context
from meta_strategy_engine import run_meta_strategy_adjustments
from thought_memory import summarize_thought_patterns


def run_background_cognition_tick():
    session_items = get_session_context(limit=8)
    if not session_items:
        return ""
    summary = summarize_thought_patterns(limit=8)
    refresh_user_identity()
    generate_initiative_from_context()
    update_knowledge_tasks_from_context()
    run_meta_strategy_adjustments()
    return summary

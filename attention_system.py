import re


HIGH_IMPACT_MARKERS = (
    "career",
    "study",
    "exam",
    "abroad",
    "job",
    "fitness",
    "gym",
    "diet",
    "money",
    "project",
    "deadline",
    "routine",
    "goal",
)

URGENT_MARKERS = ("urgent", "asap", "today", "now", "immediately", "deadline", "tomorrow")


def score_attention_priority(user_input, goal_context=None):
    text = (user_input or "").lower()
    words = re.findall(r"[a-z0-9]+", text)

    goal_relevance = 0.18 if any(marker in text for marker in HIGH_IMPACT_MARKERS) else 0.0
    if goal_context and any(token in " ".join(goal_context).lower() for token in words[:10]):
        goal_relevance += 0.24

    urgency = 0.24 if any(marker in text for marker in URGENT_MARKERS) else 0.0
    if "?" in text:
        urgency += 0.04

    long_term_impact = 0.20 if any(marker in text for marker in HIGH_IMPACT_MARKERS) else 0.0
    if any(marker in text for marker in ("choose", "vs", "should i", "roadmap", "plan")):
        long_term_impact += 0.12

    complexity_bonus = 0.08 if len(words) > 35 else 0.0
    priority = min(1.0, goal_relevance + urgency + long_term_impact + complexity_bonus)
    if priority >= 0.62:
        level = "high"
    elif priority >= 0.35:
        level = "medium"
    else:
        level = "low"
    return {
        "priority_score": round(priority, 3),
        "priority_level": level,
        "goal_relevance": round(goal_relevance, 3),
        "urgency": round(urgency, 3),
        "long_term_impact": round(long_term_impact, 3),
    }


def should_use_fast_path(user_input, goal_context=None, answer_mode="auto"):
    if isinstance(answer_mode, dict):
        if answer_mode.get("safe_mode") or answer_mode.get("force_fast"):
            selected = "quick_ollama"
        else:
            depth_mode = str(answer_mode.get("depth_mode") or "auto").strip().lower()
            if depth_mode in {"deep", "critical"}:
                selected = "deep_ollama"
            elif depth_mode in {"quick", "safe"}:
                selected = "quick_ollama"
            else:
                selected = "auto"
    else:
        selected = str(answer_mode or "auto").strip().lower()
    if selected in {"deep_ollama", "critical"}:
        return False
    if selected == "quick_ollama":
        return True
    score = score_attention_priority(user_input, goal_context=goal_context)
    return score["priority_level"] == "low"

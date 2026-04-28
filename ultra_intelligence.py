import json
import re


def estimate_confidence(question, answer, context_items=None):
    score = 0.55
    question_text = (question or "").strip().lower()
    answer_text = (answer or "").strip().lower()
    context_items = context_items or []

    if len(answer_text) > 120:
        score += 0.08
    if any(phrase in answer_text for phrase in ("i'm not sure", "i may be wrong", "might be wrong", "uncertain")):
        score -= 0.18
    if any(phrase in answer_text for phrase in ("i couldn't", "not available", "could not find", "don't have enough")):
        score -= 0.22
    if context_items:
        score += min(0.12, len(context_items) * 0.02)
    if any(word in question_text for word in ("latest", "today", "news", "weather", "price")):
        score -= 0.08
    if any(word in answer_text for word in ("step 1", "1.", "plan", "roadmap", "next")):
        score += 0.06

    return max(0.1, min(0.98, score))


def confidence_label(score):
    if score >= 0.85:
        return "high"
    if score >= 0.65:
        return "medium"
    return "low"


def format_confidence_line(score):
    percentage = int(round(score * 100))
    return f"Confidence: {percentage}% ({confidence_label(score)})."


def should_use_goal_planner(text):
    normalized = (text or "").strip().lower()
    triggers = (
        "help me become",
        "roadmap",
        "plan my",
        "study plan",
        "learning plan",
        "weekly plan",
        "long-term plan",
        "career plan",
        "how do i become",
    )
    return any(trigger in normalized for trigger in triggers)


def build_goal_roadmap(user_input, context_items=None):
    context_items = context_items or []
    goal = extract_goal_topic(user_input)
    return {
        "goal": goal,
        "mode": "dynamic_planner",
        "phases": [
            {
                "title": "Foundation",
                "duration": "Weeks 1-2",
                "steps": [
                    f"Define what success means for becoming {goal}.",
                    "Audit your current skill level, time budget, and constraints.",
                    "Pick 2-3 core resources and one practice routine.",
                ],
            },
            {
                "title": "Structured Build",
                "duration": "Weeks 3-6",
                "steps": [
                    "Break the subject into weekly themes and study blocks.",
                    "Ship one measurable practice output every week.",
                    "Review weak areas at the end of each week and adjust the next week.",
                ],
            },
            {
                "title": "Applied Depth",
                "duration": "Weeks 7-10",
                "steps": [
                    "Work on harder problems, projects, or case studies.",
                    "Document what you learn in short notes FRIDAY can reuse later.",
                    "Compare your progress against the original success definition.",
                ],
            },
            {
                "title": "Adaptive Loop",
                "duration": "Ongoing",
                "steps": [
                    "Keep the strongest habits, drop weak routines, and raise difficulty slowly.",
                    "Track wins, blockers, and questions so the plan stays personalized.",
                    "Ask FRIDAY to regenerate the roadmap whenever your goal or schedule changes.",
                ],
            },
        ],
        "context_used": context_items[:6],
    }


def render_goal_roadmap(roadmap):
    lines = [
        f"Goal roadmap: {roadmap.get('goal', 'your goal')}",
        "Mode: Dynamic planner",
    ]
    for index, phase in enumerate(roadmap.get("phases", []), start=1):
        lines.append(f"{index}. {phase.get('title', '')} ({phase.get('duration', '')})")
        for step in phase.get("steps", [])[:3]:
            lines.append(f"- {step}")
    lines.append("If you want, I can turn this into a tighter week-by-week plan next.")
    return "\n".join(lines)


def extract_goal_topic(text):
    cleaned = (text or "").strip()
    patterns = [
        r"help me become (.+)",
        r"how do i become (.+)",
        r"plan my (.+)",
        r"create a roadmap for (.+)",
        r"roadmap for (.+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            return match.group(1).strip(" .?!")
    return cleaned.strip(" .?!") or "your goal"


def parse_json_object(text):
    cleaned = (text or "").strip()
    if not cleaned:
        return {}
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(cleaned[start:end + 1])
        except Exception:
            return {}
    return {}

import math


def clamp_confidence(value):
    return max(0.05, min(0.98, float(value or 0.0)))


def estimate_response_confidence(
    memory_context=None,
    candidate_answers=None,
    selected_answer="",
    used_live_answer=False,
    used_web_fallback=False,
    knowledge_gap=False,
    debate_used=False,
):
    memory_count = len(memory_context or [])
    candidate_count = len(candidate_answers or [])
    answer_length = len((selected_answer or "").strip())

    score = 0.38
    score += min(0.22, memory_count * 0.02)
    score += min(0.16, max(candidate_count - 1, 0) * 0.06)
    score += min(0.10, answer_length / 8000)

    if debate_used:
        score += 0.07
    if used_live_answer:
        score -= 0.06
    if used_web_fallback:
        score -= 0.12
    if knowledge_gap:
        score -= 0.18

    return clamp_confidence(score)


def format_confidence_percent(confidence):
    return f"{int(round(clamp_confidence(confidence) * 100))}%"


def build_uncertainty_note(confidence, knowledge_gap=False, used_web_fallback=False):
    confidence = clamp_confidence(confidence)
    if knowledge_gap:
        return "This may need verification because I can see a knowledge gap."
    if used_web_fallback:
        return "This answer relies on fallback search and may still need verification."
    if confidence < 0.45:
        return "I may be missing context here, so treat this as a best-effort answer."
    if confidence < 0.7:
        return "I’m moderately confident, but some parts may need verification."
    return ""


def append_confidence_block(answer, confidence, uncertainty_note=""):
    text = (answer or "").strip()
    if not text:
        return ""

    lines = [text, "", f"Confidence: {format_confidence_percent(confidence)}."]
    if uncertainty_note:
        lines.append(uncertainty_note.strip())
    return "\n".join(lines).strip()

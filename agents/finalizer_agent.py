from confidence_engine import build_uncertainty_note
from control_profile import build_response_style_prompt, normalize_control_mode
from llm_router import ask_friday_llm_ultra
from ultra_intelligence import parse_json_object


def finalize_response(
    user_input,
    candidate_answer,
    confidence,
    uncertainty_note="",
    goal_context=None,
    evolution_rules=None,
    long_term_note="",
    control_mode=None,
):
    control = normalize_control_mode(control_mode)
    goal_text = "\n".join(goal_context or [])
    rules_text = "\n".join(evolution_rules or [])
    prompt = f"""
User request:
{user_input}

Candidate answer:
{candidate_answer}

Confidence:
{confidence:.2f}

Uncertainty:
{uncertainty_note or 'None'}

Goal context:
{goal_text or 'None'}

Evolution rules:
{rules_text or 'None'}

Long-term impact note:
{long_term_note or 'None'}
""".strip()

    extra_system_prompt = """
You are FRIDAY's finalizer agent.
Decide the best response strategy:
- answer
- clarify
- challenge
- act

Your responsibilities:
- tone optimization
- intelligence compression
- strategic response selection
- deciding if the answer should be shorter
- deciding if a clarification question is smarter

Return strict JSON with keys:
- response_type
- final_answer
- finalizer_decision
""".strip()
    style_prompt = build_response_style_prompt(control)
    if style_prompt:
        extra_system_prompt += "\n\n" + style_prompt

    if control["safe_mode"] or control["force_fast"]:
        return heuristic_finalize_response(user_input, candidate_answer, confidence, uncertainty_note, long_term_note, control_mode=control)

    answer, _, _ = ask_friday_llm_ultra(prompt, extra_system_prompt=extra_system_prompt, control_mode=control)
    if answer:
        parsed = parse_json_object(answer)
        final_answer = (parsed.get("final_answer") or "").strip()
        response_type = (parsed.get("response_type") or "answer").strip().lower()
        decision = (parsed.get("finalizer_decision") or "").strip()
        if final_answer:
            return {
                "response_type": response_type if response_type in {"answer", "clarify", "challenge", "act"} else "answer",
                "final_answer": final_answer,
                "finalizer_decision": decision or "Finalizer selected the strongest reply form.",
            }

    return heuristic_finalize_response(user_input, candidate_answer, confidence, uncertainty_note, long_term_note, control_mode=control)


def heuristic_finalize_response(user_input, candidate_answer, confidence, uncertainty_note="", long_term_note="", control_mode=None):
    control = normalize_control_mode(control_mode)
    lowered = (user_input or "").lower()
    response_type = "answer"
    final_text = (candidate_answer or "").strip()
    decision = "Heuristic finalizer kept the refined answer."

    risky_markers = ("shortcut", "pass exam", "skip gym", "ignore", "hack")
    compare_markers = ("which is better", "better biotech or nursing", "choose between")

    if any(marker in lowered for marker in risky_markers):
        response_type = "challenge"
        decision = "Finalizer chose a challenge response because the request risks poor long-term outcomes."
        final_text = "That shortcut may hurt your long-term outcome. Want the strongest sustainable strategy instead?"
    elif any(marker in lowered for marker in compare_markers):
        response_type = "clarify"
        decision = "Finalizer chose clarification because the better option depends on your long-term goal."
        final_text = "The better option depends on your goal, budget, and abroad plan. Want me to compare them for your exact situation?"
    elif confidence < 0.46:
        response_type = "clarify"
        decision = "Finalizer chose clarification because confidence is low."
        final_text = "I may be missing important context here. Want to give me one more detail so I can answer this properly?"

    if control["response_style"] == "one_line":
        final_text = final_text.replace("\n", " ").strip()
    elif control["response_style"] == "bullet" and "\n-" not in final_text:
        parts = [part.strip() for part in final_text.split(". ") if part.strip()]
        final_text = "\n".join(f"- {part.rstrip('.')}" for part in parts[:5]) or final_text
    elif control["response_style"] == "analytical" and "Tradeoff:" not in final_text:
        final_text = f"Tradeoff view: {final_text}".strip()

    if uncertainty_note and uncertainty_note.lower() not in final_text.lower():
        final_text = f"{final_text}\n\n{uncertainty_note}".strip()
    if long_term_note and long_term_note.lower() not in final_text.lower():
        final_text = f"{final_text}\n\nLong-term view: {long_term_note}".strip()

    return {
        "response_type": response_type,
        "final_answer": final_text,
        "finalizer_decision": decision,
    }

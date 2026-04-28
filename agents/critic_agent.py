from llm_router import ask_friday_llm_ultra
from ultra_intelligence import parse_json_object


def critique_and_refine_answer(user_input, candidates, memory_context=None, goal_context=None):
    candidate_lines = []
    for index, item in enumerate(candidates or [], start=1):
        source = item.get("source", f"candidate-{index}")
        answer = (item.get("answer") or "").strip()
        if answer:
            candidate_lines.append(f"{source}:\n{answer}")

    if not candidate_lines:
        return {"final_answer": "", "critique": "", "hallucination_risk": "high", "confidence_adjustment": -0.12}

    memory_text = "\n".join(memory_context or [])
    goal_text = "\n".join(goal_context or [])
    prompt = f"""
User request:
{user_input}

Memory context:
{memory_text or 'None'}

Goal context:
{goal_text or 'None'}

Candidate answers:
{chr(10).join(candidate_lines)}
""".strip()

    extra_system_prompt = """
You are FRIDAY's critic loop.
Your job:
- detect weak logic
- flag hallucination risk
- improve clarity
- merge the strongest answer into one final answer

Return strict JSON with keys:
- critique
- final_answer
- hallucination_risk
- confidence_adjustment

Use hallucination_risk as one of: low, medium, high
Use confidence_adjustment as a number between -0.25 and 0.15
""".strip()

    answer, _, _ = ask_friday_llm_ultra(prompt, extra_system_prompt=extra_system_prompt)
    if not answer:
        best = max(candidates, key=lambda item: len((item.get("answer") or "").strip()))
        return {
            "final_answer": (best.get("answer") or "").strip(),
            "critique": "Critic loop fallback selected the strongest available draft.",
            "hallucination_risk": "medium",
            "confidence_adjustment": -0.03,
        }

    parsed = parse_json_object(answer)
    final_answer = (parsed.get("final_answer") or "").strip()
    critique = (parsed.get("critique") or "").strip()
    hallucination_risk = (parsed.get("hallucination_risk") or "medium").strip().lower()
    adjustment = parsed.get("confidence_adjustment", 0.0)
    try:
        adjustment = float(adjustment)
    except Exception:
        adjustment = 0.0

    if not final_answer:
        best = max(candidates, key=lambda item: len((item.get("answer") or "").strip()))
        final_answer = (best.get("answer") or "").strip()

    return {
        "final_answer": final_answer,
        "critique": critique,
        "hallucination_risk": hallucination_risk if hallucination_risk in {"low", "medium", "high"} else "medium",
        "confidence_adjustment": adjustment,
    }

from identity_model import load_user_identity


def should_simulate(user_input):
    lowered = (user_input or "").lower()
    markers = (
        "should i",
        "skip gym",
        "choose",
        "vs",
        "what if",
        "if i",
        "decision",
        "worth it",
    )
    return any(marker in lowered for marker in markers)


def simulate_outcome(user_input, goal_context=None):
    lowered = (user_input or "").lower()
    identity = load_user_identity()
    discipline = (identity.get("discipline_level") or "developing").lower()
    risk = (identity.get("risk_tolerance") or "balanced").lower()
    goals = ", ".join(identity.get("goals") or [])

    short_term = "This choice may feel convenient now."
    long_term = "Its long-term effect depends on whether it supports your bigger direction."

    if "skip gym" in lowered:
        short_term = "Short-term, you save energy today but lose momentum."
        long_term = "Long-term, repeated skips make consistency fragile and slow visible progress."
    elif any(word in lowered for word in ("biotech", "nursing", "career", "abroad")):
        short_term = "Short-term, picking the clearer-fit path reduces confusion and speeds your next preparation step."
        long_term = "Long-term, the better choice is the one that compounds into exam readiness, job alignment, and abroad options."
    elif any(word in lowered for word in ("buy", "spend", "money")):
        short_term = "Short-term, the purchase may solve an immediate want."
        long_term = "Long-term, it is only a good decision if it still feels aligned with your priorities after the impulse passes."

    bias = "You tend to benefit from structure and consistency." if discipline != "high" else "You can usually handle disciplined long-term plans."
    if risk == "cautious":
        bias += " Safer options are more likely to fit your style."
    if goals:
        bias += f" Current goals in view: {goals}."

    lines = [
        "Decision simulation:",
        f"Short-term effect: {short_term}",
        f"Long-term effect: {long_term}",
        f"Personal fit: {bias}",
    ]
    if goal_context:
        lines.append("Goal context: " + " ".join(goal_context[:2]))
    return "\n".join(lines)

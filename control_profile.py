def normalize_control_mode(answer_mode=None):
    if isinstance(answer_mode, dict):
        data = dict(answer_mode)
    else:
        selected = (answer_mode or "auto").strip().lower() if isinstance(answer_mode, str) else "auto"
        mapping = {
            "auto": {"depth_mode": "smart"},
            "quick_ollama": {"depth_mode": "quick"},
            "deep_ollama": {"depth_mode": "deep"},
            "wiki_search": {"depth_mode": "smart", "router_mode": "wiki_search"},
            "safe_mode": {"depth_mode": "safe", "safe_mode": True},
            "intermediate_power": {"depth_mode": "deep", "ollama_strategy": "deep", "mode_label": "INTERMEDIATE POWER", "badge_label": "Intermediate Power"},
            "research": {"depth_mode": "deep", "ollama_strategy": "deep", "full_research": True, "mode_label": "RESEARCH", "badge_label": "Research"},
        }
        data = mapping.get(selected, {"depth_mode": "smart"})

    profile = {
        "depth_mode": (data.get("depth_mode") or "smart").strip().lower(),
        "response_style": (data.get("response_style") or "default").strip().lower(),
        "force_fast": bool(data.get("force_fast", False)),
        "safe_mode": bool(data.get("safe_mode", False)),
        "ask_better_question": bool(data.get("ask_better_question", False)),
        "router_mode": (data.get("router_mode") or "").strip().lower(),
        "refine_last": bool(data.get("refine_last", False)),
        "ollama_strategy": (data.get("ollama_strategy") or "").strip().lower(),
        "mode_label": (data.get("mode_label") or "").strip(),
        "badge_label": (data.get("badge_label") or "").strip(),
        "full_research": bool(data.get("full_research", False)),
    }

    if profile["depth_mode"] not in {"quick", "smart", "deep", "safe"}:
        profile["depth_mode"] = "smart"
    if profile["response_style"] not in {"default", "bullet", "explanation", "one_line", "analytical"}:
        profile["response_style"] = "default"
    if profile["depth_mode"] == "safe":
        profile["safe_mode"] = True
        profile["force_fast"] = True
    return profile


def profile_to_label(profile):
    data = normalize_control_mode(profile)
    if data.get("mode_label"):
        return data["mode_label"]
    depth = {
        "quick": "QUICK",
        "smart": "SMART",
        "deep": "DEEP",
        "safe": "SAFE",
    }.get(data["depth_mode"], "SMART")
    style = {
        "default": "DEFAULT",
        "bullet": "BULLET",
        "explanation": "EXPLAIN",
        "one_line": "ONE-LINE",
        "analytical": "ANALYTICAL",
    }.get(data["response_style"], "DEFAULT")
    return f"{depth} / {style}"


def build_response_style_prompt(profile):
    data = normalize_control_mode(profile)
    style = data["response_style"]
    lines = []
    if style == "bullet":
        lines.append("Format the answer as short flat bullet points.")
    elif style == "explanation":
        lines.append("Explain clearly in a short teaching style.")
    elif style == "one_line":
        lines.append("Answer in one line if possible.")
    elif style == "analytical":
        lines.append("Answer analytically, focusing on tradeoffs and reasoning.")
    if data["ask_better_question"]:
        lines.append("Do not answer directly first. Give the user a sharper version of their question, then a short note on why it is better.")
    if data["force_fast"]:
        lines.append("Prioritize speed and compactness over completeness.")
    if data["safe_mode"]:
        lines.append("Operate in safe mode: minimize latency, avoid deep chains, and keep the answer conservative.")
    return "\n".join(lines).strip()


def answer_badge(profile):
    data = normalize_control_mode(profile)
    if data.get("badge_label"):
        return data["badge_label"]
    depth = data["depth_mode"]
    return {
        "quick": "Quick Answer",
        "smart": "Smart Answer",
        "deep": "Deep Answer",
        "safe": "Safe Answer",
    }.get(depth, "Smart Answer")

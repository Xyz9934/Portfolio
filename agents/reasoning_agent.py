import re

from agents.critic_agent import critique_and_refine_answer
from agents.finalizer_agent import finalize_response
from agents.simulation_agent import should_simulate, simulate_outcome
from attention_system import score_attention_priority, should_use_fast_path
from assistant_brain import get_assistant_context, handle_assistant_command
from assistant_memory import get_feedback_context, get_session_context, record_feedback_correction, save_goal_roadmap
from autonomous_mode import run_autonomous_pipeline, should_use_autonomous_mode
from confidence_engine import append_confidence_block, build_uncertainty_note, clamp_confidence, estimate_response_confidence, format_confidence_percent
from control_profile import build_response_style_prompt, normalize_control_mode
from debug_runtime import write_debug_snapshot
from evolution_engine import get_rule_context, learn_rules_from_turn
from execution_governor import build_execution_budget, budget_exceeded, can_use_stage
from execution_feedback import get_execution_feedback_context
from fast_cache import get_cached_response, put_cached_response
from identity_model import render_identity_context
from intelligence_metrics import estimate_metric_bundle, log_response_metric
from internet_brain import can_handle_live_query, handle_live_query
from knowledge_expansion import enqueue_knowledge_task
from life_brain import get_active_goals, get_goal_roadmap, get_life_brain_context, record_habit_event, set_goal
from llm_router import ask_friday_llm_mode, ask_friday_llm_ultra, assess_request_complexity
from memory_guard import is_relevant_match
from memory_search import search_memory
from private_knowledge import render_private_knowledge_context
from search_brain import search_web
from semantic_brain import learn_text
from thought_memory import get_recent_reasoning_patterns, log_reasoning_trace
from ultra_intelligence import build_goal_roadmap, render_goal_roadmap, should_use_goal_planner


FALLBACK_PHRASES = (
    "no_memory_answer",
    "no info",
    "no information",
    "not enough information",
    "don't have information",
    "do not have information",
    "cannot find",
    "can't find",
    "not in the context",
    "not in the provided context",
    "based on the pdf",
    "from the pdf",
    "the pdf you have provided",
)


def handle_reasoning_task(user_input, task=None, answer_mode="auto"):
    control = normalize_control_mode(answer_mode)
    query_profile = analyze_query_profile(user_input)
    if is_simple_greeting(user_input):
        return ensure_response_guarantee(respond_to_greeting(user_input), user_input, control)

    if control.get("router_mode") == "wiki_search" or answer_mode == "wiki_search":
        wiki_text, used_web = fallback_answer(user_input, answer_mode=answer_mode)
        if used_web:
            return {"message": wiki_text, "response_style": "system"}
        return wiki_text

    feedback_entry = record_feedback_correction(user_input)
    if feedback_entry:
        if feedback_entry.get("feedback_type") == "style":
            preference_value = (feedback_entry.get("preference_value") or "").strip()
            if preference_value:
                return f"Understood. I'll remember that style preference and aim for {preference_value} from now on."
            return "Understood. I saved that response-style preference and I'll use it going forward."
        correction = (feedback_entry.get("correction") or "").strip()
        if correction:
            return "Thanks. I saved that correction and I'll use it to avoid repeating the same mistake."
        return "Thanks. I marked that previous answer as incorrect and I'll use that feedback going forward."

    assistant_reply = handle_assistant_command(user_input)
    if assistant_reply:
        return assistant_reply

    if can_handle_live_query(user_input):
        live_answer = handle_live_query(user_input)
        if live_answer:
            return live_answer

    active_goal_context = build_goal_priority_context(user_input)
    attention = score_attention_priority(user_input, goal_context=active_goal_context)
    complexity = assess_request_complexity(user_input, "\n".join(active_goal_context[:4]))
    if control.get("depth_mode") == "safe":
        attention["priority_level"] = "low"
    budget = build_execution_budget(control, priority_level=attention.get("priority_level", "medium"))
    cached = get_cached_response(user_input, control_mode=control)
    if cached:
        return ensure_response_guarantee(cached, user_input, control)

    curiosity_question = maybe_ask_clarifying_question(user_input, attention, complexity, control)
    if curiosity_question:
        confidence = 0.78
        metric_bundle = estimate_metric_bundle(user_input, curiosity_question, confidence, response_type="clarify")
        log_response_metric(user_input, "clarify", confidence, **metric_bundle)
        write_debug_snapshot(
            {
                "mode": answer_mode,
                "complexity": complexity,
                "response_type": "clarify",
                "confidence": format_confidence_percent(confidence),
                "draft_a": "",
                "draft_b": "",
                "critic": "Curiosity engine triggered before full answer generation.",
                "finalizer_decision": "Ask one clarifying question first.",
                "final_answer": curiosity_question,
            }
        )
        return ensure_response_guarantee(curiosity_question, user_input, control)

    if should_use_fast_path(user_input, goal_context=active_goal_context, answer_mode=control):
        return ensure_response_guarantee(handle_fast_response(user_input, active_goal_context, attention, answer_mode=control, complexity=complexity), user_input, control)

    evolution_rules = get_rule_context(limit=6)
    life_context = get_life_brain_context(limit=6) if query_profile["allow_life_context"] else []
    private_context = render_private_knowledge_context(user_input, limit=4)
    identity_context = render_identity_context() if query_profile["allow_identity_context"] else []
    assistant_context = get_assistant_context(user_input)
    feedback_context = get_feedback_context(user_input, limit=3)
    session_context = get_session_context(limit=6) if query_profile["allow_session_context"] else []
    memory_hits = []
    if can_use_stage(budget, "deep_memory") and query_profile["allow_deep_memory"]:
        memory_hits = search_memory(user_input, top_k=min(5, int(budget.get("max_memory_fetch", 5))))
    memories = (
        feedback_context
        + evolution_rules
        + active_goal_context
        + identity_context
        + life_context
        + private_context
        + session_context
        + assistant_context
        + memory_hits
        + get_execution_feedback_context(limit=4)
        + get_recent_reasoning_patterns(limit=4)
    )
    merged = dedupe_items(memories, limit=18)

    if should_use_autonomous_mode(user_input):
        pipeline_text, _ = run_autonomous_pipeline(
            user_input,
            private_context=private_context,
            life_context=life_context,
            memory_context=merged,
        )
        return ensure_response_guarantee(pipeline_text, user_input, control)

    if should_use_goal_planner(user_input):
        roadmap = build_goal_roadmap(user_input, merged)
        roadmap_text = render_goal_roadmap(roadmap)
        save_goal_roadmap(roadmap.get("goal", ""), roadmap_text)
        set_goal(roadmap.get("goal", ""), roadmap=roadmap_text, progress_note="Roadmap created by FRIDAY.")
        confidence = estimate_response_confidence(
            memory_context=merged,
            candidate_answers=[{"source": "goal-roadmap", "answer": roadmap_text}],
            selected_answer=roadmap_text,
        )
        future_step = build_future_prediction(user_input, roadmap_text, active_goal_context)
        final_text = append_confidence_block(roadmap_text, confidence)
        if future_step:
            final_text += "\n\nNext likely step: " + future_step
        put_cached_response(user_input, final_text, control_mode=control)
        return ensure_response_guarantee(final_text, user_input, control)

    if detect_intent_override(user_input, active_goal_context):
        final_text = "That path may hurt your long-term outcome. Want the strongest sustainable strategy instead?"
        confidence = 0.76
        metric_bundle = estimate_metric_bundle(user_input, final_text, confidence, response_type="challenge")
        log_response_metric(user_input, "challenge", confidence, **metric_bundle)
        write_debug_snapshot(
            {
                "mode": answer_mode,
                "complexity": complexity,
                "response_type": "challenge",
                "confidence": format_confidence_percent(confidence),
                "draft_a": "",
                "draft_b": "",
                "critic": "Intent override system intercepted a risky request.",
                "finalizer_decision": "Override triggered before normal answer generation.",
                "final_answer": final_text,
            }
        )
        put_cached_response(user_input, final_text, control_mode=control)
        return ensure_response_guarantee(final_text, user_input, control)

    goal_follow_up = maybe_answer_from_active_goal(user_input)
    if goal_follow_up:
        confidence = estimate_response_confidence(
            memory_context=merged,
            candidate_answers=[{"source": "goal-follow-up", "answer": goal_follow_up}],
            selected_answer=goal_follow_up,
        )
        final_text = append_confidence_block(goal_follow_up, confidence)
        future_step = build_future_prediction(user_input, goal_follow_up, active_goal_context)
        if future_step:
            final_text += "\n\nNext likely step: " + future_step
        put_cached_response(user_input, final_text, control_mode=control)
        return ensure_response_guarantee(final_text, user_input, control)

    knowledge_gap = detect_knowledge_gap(user_input, merged)
    if knowledge_gap:
        topic = detect_primary_topic(user_input)
        if topic:
            enqueue_knowledge_task(topic, reason="live_reasoning_gap")
    candidates = []

    memory_answer = answer_from_memory_context(user_input, merged, answer_mode=control, complexity=complexity)
    if memory_answer != "NO_MEMORY_ANSWER" and not should_fallback(memory_answer):
        candidates.append({"source": "memory_agent", "answer": memory_answer})

    reasoning_answer = build_reasoning_candidate(
        user_input,
        merged,
        active_goal_context,
        evolution_rules,
        knowledge_gap,
        answer_mode=control,
        complexity=complexity,
    )
    if reasoning_answer and not should_fallback(reasoning_answer):
        candidates.append({"source": "reasoning_agent", "answer": reasoning_answer})

    if not candidates:
        fallback_text, used_web = fallback_answer(user_input, answer_mode=answer_mode)
        confidence = estimate_response_confidence(
            memory_context=merged,
            selected_answer=fallback_text,
            used_web_fallback=used_web,
            knowledge_gap=True,
        )
        uncertainty_note = build_uncertainty_note(confidence, knowledge_gap=True, used_web_fallback=used_web)
        long_term_note = build_long_term_projection(user_input, active_goal_context)
        simulation_note = simulate_outcome(user_input, active_goal_context) if should_simulate(user_input) else ""
        finalizer = finalize_response(
            user_input,
            fallback_text,
            confidence,
            uncertainty_note=uncertainty_note,
            goal_context=active_goal_context,
            evolution_rules=evolution_rules,
            long_term_note=join_notes(long_term_note, simulation_note),
            control_mode=control,
        )
        final_text = append_confidence_block(finalizer["final_answer"], confidence, uncertainty_note)
        future_step = build_future_prediction(user_input, fallback_text, active_goal_context)
        if future_step:
            final_text += "\n\nNext likely step: " + future_step
        if simulation_note and simulation_note.lower() not in final_text.lower():
            final_text += "\n\n" + simulation_note
        elif long_term_note and long_term_note.lower() not in final_text.lower():
            final_text += "\n\nLong-term view: " + long_term_note
        learn_rules_from_turn(user_input, final_text, confidence)
        metric_bundle = estimate_metric_bundle(user_input, final_text, confidence, response_type=finalizer["response_type"])
        log_response_metric(user_input, finalizer["response_type"], confidence, **metric_bundle)
        log_reasoning_trace(user_input, final_answer=final_text, critique="Fallback answer used.", confidence=confidence, alternatives=[])
        write_debug_snapshot(
            {
                "mode": answer_mode,
                "complexity": complexity,
                "response_type": finalizer["response_type"],
                "confidence": format_confidence_percent(confidence),
                "draft_a": "",
                "draft_b": "",
                "critic": "Fallback answer path used.",
                "finalizer_decision": finalizer.get("finalizer_decision", ""),
                "final_answer": final_text,
            }
        )
        put_cached_response(user_input, final_text, control_mode=control)
        return ensure_response_guarantee(final_text, user_input, control)

    if can_use_stage(budget, "critic"):
        critic_result = critique_and_refine_answer(user_input, candidates, memory_context=merged, goal_context=active_goal_context)
        refined_answer = (critic_result.get("final_answer") or "").strip()
    else:
        critic_result = {"critique": "Execution governor skipped critic for latency control.", "confidence_adjustment": -0.04, "hallucination_risk": "medium"}
        refined_answer = ""
    if not refined_answer:
        refined_answer = max(candidates, key=lambda item: len((item.get("answer") or "").strip())).get("answer", "").strip()

    debate_used = len(candidates) > 1
    confidence = estimate_response_confidence(
        memory_context=merged,
        candidate_answers=candidates,
        selected_answer=refined_answer,
        knowledge_gap=knowledge_gap,
        debate_used=debate_used,
    )
    confidence = clamp_confidence(confidence + float(critic_result.get("confidence_adjustment") or 0.0))

    hallucination_risk = critic_result.get("hallucination_risk", "medium")
    uncertainty_note = build_uncertainty_note(
        confidence,
        knowledge_gap=knowledge_gap or hallucination_risk == "high",
        used_web_fallback=False,
    )
    if hallucination_risk == "medium" and not uncertainty_note and confidence < 0.8:
        uncertainty_note = "Some parts of this answer are inferred rather than directly verified."

    long_term_note = build_long_term_projection(user_input, active_goal_context)
    simulation_note = simulate_outcome(user_input, active_goal_context) if should_simulate(user_input) else ""
    finalizer = finalize_response(
        user_input,
        refined_answer,
        confidence,
        uncertainty_note=uncertainty_note,
        goal_context=active_goal_context,
        evolution_rules=evolution_rules,
        long_term_note=join_notes(long_term_note, simulation_note),
        control_mode=control,
    )
    final_answer = finalizer.get("final_answer", refined_answer).strip() or refined_answer

    maybe_record_habit_signal(user_input)
    final_text = append_confidence_block(final_answer, confidence, uncertainty_note)
    future_step = build_future_prediction(user_input, final_answer, active_goal_context)
    if future_step and future_step.lower() not in final_text.lower():
        final_text += "\n\nNext likely step: " + future_step
    if simulation_note and simulation_note.lower() not in final_text.lower():
        final_text += "\n\n" + simulation_note
    elif long_term_note and long_term_note.lower() not in final_text.lower():
        final_text += "\n\nLong-term view: " + long_term_note

    learn_rules_from_turn(user_input, final_text, confidence)
    metric_bundle = estimate_metric_bundle(user_input, final_text, confidence, response_type=finalizer["response_type"])
    log_response_metric(user_input, finalizer["response_type"], confidence, **metric_bundle)
    log_reasoning_trace(
        user_input,
        draft_answer=candidates[0].get("answer", ""),
        final_answer=final_text,
        critique=critic_result.get("critique", ""),
        confidence=confidence,
        alternatives=[item.get("answer", "") for item in candidates[1:]],
    )
    write_debug_snapshot(
        {
            "mode": answer_mode,
            "complexity": complexity,
            "response_type": finalizer["response_type"],
            "confidence": format_confidence_percent(confidence),
            "draft_a": candidates[0].get("answer", ""),
            "draft_b": candidates[1].get("answer", "") if len(candidates) > 1 else "",
            "critic": critic_result.get("critique", ""),
            "finalizer_decision": finalizer.get("finalizer_decision", ""),
            "final_answer": final_text,
        }
    )
    put_cached_response(user_input, final_text, control_mode=control)
    return ensure_response_guarantee(final_text, user_input, control)


def dedupe_items(items, limit=16):
    merged = []
    for item in items:
        if item and item not in merged:
            merged.append(item)
    return merged[:limit]


def answer_from_memory_context(question, memories, answer_mode="auto", complexity="medium"):
    context = "\n\n".join(memories)
    if not context.strip():
        if memories and is_relevant_match(question, memories[0], strict=False):
            return memories[0].strip()
        return "NO_MEMORY_ANSWER"

    prompt = f"""
Memory context:
{context}

User question:
{question}
""".strip()
    extra_system_prompt = """
Think carefully before answering.
Use the memory context only if it is actually relevant to the user's question.
If feedback memory is present, treat it as a correction signal and avoid repeating the same mistake.
If style feedback memory is present, adapt the answer style to match it.
If the memory context is not relevant or does not answer the question, respond with exactly:
NO_MEMORY_ANSWER
Then answer naturally with FRIDAY personality.
""".strip()

    control = normalize_control_mode(answer_mode)
    model_mode = resolve_model_mode(control, complexity)
    if model_mode in {"quick_ollama", "deep_ollama"}:
        answer, _, _ = ask_friday_llm_mode(prompt, mode=control if isinstance(answer_mode, dict) else model_mode, extra_system_prompt=merge_system_prompts(extra_system_prompt, build_response_style_prompt(control)))
    else:
        answer, _, _ = ask_friday_llm_ultra(prompt, extra_system_prompt=merge_system_prompts(extra_system_prompt, build_response_style_prompt(control)), control_mode=control)
    if answer:
        cleaned = answer.strip()
        if "NO_MEMORY_ANSWER" in cleaned:
            return "NO_MEMORY_ANSWER"
        return cleaned
    return "NO_MEMORY_ANSWER"


def should_fallback(answer):
    if not answer or not answer.strip():
        return True
    normalized = answer.lower()
    return any(phrase in normalized for phrase in FALLBACK_PHRASES)


def is_simple_greeting(user_input):
    normalized = normalize_text(user_input)
    if not normalized:
        return False

    greeting_phrases = {
        "hi",
        "hello",
        "hey",
        "hey there",
        "hi there",
        "hello there",
        "hello babe",
        "hi babe",
        "hey babe",
        "hello baby",
        "hi baby",
        "hey baby",
    }
    if normalized in greeting_phrases:
        return True

    tokens = normalized.split()
    if len(tokens) <= 3 and tokens[0] in {"hi", "hello", "hey"}:
        return True
    return False


def respond_to_greeting(user_input):
    normalized = normalize_text(user_input)
    if any(term in normalized for term in ("babe", "baby", "love", "sweetheart")):
        return "You're cute 🙂 What's up?"
    return "Hey 🙂 What's up?"


def normalize_text(text):
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def fallback_answer(question, answer_mode="auto"):
    web_answer = search_web(question)
    if web_answer and "could not" not in web_answer.lower() and not web_answer.lower().startswith("search error"):
        try:
            learn_text(web_answer)
        except Exception:
            pass
        if answer_mode == "wiki_search":
            return web_answer, True
        return "I couldn't answer that from memory, but I found this online:\n\n" + web_answer, True
    return "I couldn't find a reliable answer in memory or online.", False


def maybe_answer_from_active_goal(user_input):
    if not analyze_query_profile(user_input)["goal_relevant"]:
        return ""
    lowered = normalize_text(user_input)
    goal_triggers = ("my goal", "my plan", "my roadmap", "how am i doing", "what should i do next")
    if not any(trigger in lowered for trigger in goal_triggers):
        return ""
    goals = get_active_goals(limit=1)
    if not goals:
        return ""
    goal = goals[0]
    roadmap = get_goal_roadmap(goal.get("goal_name", ""))
    lines = [f"Your active goal is `{goal.get('goal_name', '')}`."]
    if goal.get("progress_note"):
        lines.append(f"Latest progress note: {goal.get('progress_note', '')}")
    if roadmap:
        lines.append("Next move: review the current roadmap and pick the smallest concrete action you can finish today.")
    lines.append("If you want, I can turn that into a tighter action list for today.")
    return "\n".join(lines)


def maybe_record_habit_signal(user_input):
    lowered = normalize_text(user_input)
    if "gym" in lowered:
        record_habit_event("gym", event_type="mentioned", note=user_input)
    if any(word in lowered for word in ("study", "exam", "revision")):
        record_habit_event("study", event_type="mentioned", note=user_input)
    if any(word in lowered for word in ("code", "coding", "project", "debug")):
        record_habit_event("coding", event_type="mentioned", note=user_input)


def build_goal_priority_context(user_input=""):
    if not analyze_query_profile(user_input)["goal_relevant"]:
        return []
    goals = get_active_goals(limit=3)
    context = []
    for item in goals:
        goal_name = (item.get("goal_name") or "").strip()
        progress_note = (item.get("progress_note") or "").strip()
        if goal_name:
            line = f"Active goal priority: {goal_name}."
            if progress_note:
                line += f" Latest progress: {progress_note}."
            context.append(line)
    return context


def detect_knowledge_gap(user_input, memories):
    lowered = normalize_text(user_input)
    ambiguity_markers = ("latest", "current", "today", "right now", "recent", "news")
    if any(marker in lowered for marker in ambiguity_markers):
        return True
    if len(memories or []) < 2 and len(lowered.split()) > 6:
        return True
    return False


def resolve_model_mode(answer_mode, complexity):
    control = normalize_control_mode(answer_mode)
    if control.get("full_research"):
        return "critical"
    if control.get("router_mode") == "wiki_search":
        return "wiki_search"
    if control["safe_mode"] or control["force_fast"] or control["depth_mode"] in {"quick", "safe"}:
        return "quick_ollama"
    if control["depth_mode"] == "deep":
        return "critical" if complexity == "critical" else "deep_ollama"
    if complexity in {"simple", "medium"}:
        return "quick_ollama"
    if complexity == "complex":
        return "deep_ollama"
    return "critical"


def build_reasoning_candidate(user_input, memories, goal_context, evolution_rules, knowledge_gap=False, answer_mode="auto", complexity="medium"):
    context = "\n\n".join((memories or [])[:16])
    goals = "\n".join(goal_context or [])
    rules = "\n".join(evolution_rules or [])
    prompt = f"""
Relevant context:
{context or 'None'}

Goal priorities:
{goals or 'None'}

Evolution rules:
{rules or 'None'}

User request:
{user_input}
""".strip()

    extra_system_prompt = """
Produce a direct draft answer for the user.
Think carefully and stay grounded in the provided context.
If context is thin, be honest and avoid pretending certainty.
When helpful, choose the strategically best response instead of the most obvious one.
""".strip()
    if knowledge_gap:
        extra_system_prompt += "\n\nA knowledge gap is suspected, so avoid overclaiming and prefer cautious wording."

    control = normalize_control_mode(answer_mode)
    extra_system_prompt = merge_system_prompts(extra_system_prompt, build_response_style_prompt(control))
    model_mode = resolve_model_mode(control, complexity)
    if model_mode in {"quick_ollama", "deep_ollama"}:
        answer, _, _ = ask_friday_llm_mode(prompt, mode=control, extra_system_prompt=extra_system_prompt)
    elif model_mode == "critical":
        answer, _, _ = ask_friday_llm_ultra(prompt, extra_system_prompt=extra_system_prompt, control_mode=control)
    else:
        answer, _, _ = ask_friday_llm_mode(prompt, mode=control, extra_system_prompt=extra_system_prompt)
    return (answer or "").strip()


def build_future_prediction(user_input, answer_text, goal_context):
    if not analyze_query_profile(user_input)["goal_relevant"]:
        return ""
    lowered = normalize_text(user_input + "\n" + answer_text + "\n" + "\n".join(goal_context or []))
    if any(word in lowered for word in ("study", "biotech", "exam", "college", "career")):
        return "You may want entrance exam details, a roadmap, or the next concrete study step."
    if any(word in lowered for word in ("gym", "fitness", "diet", "workout", "muscle")):
        return "A useful next move would be turning this into a workout, diet, or weekly consistency plan."
    if any(word in lowered for word in ("code", "project", "debug", "python", "app")):
        return "The next step is usually implementation, debugging, or turning this into a concrete task list."
    if any(word in lowered for word in ("routine", "remind", "schedule", "automation")):
        return "You may want this converted into a routine, reminder, or automated action."
    return ""


def build_long_term_projection(user_input, goal_context):
    if not analyze_query_profile(user_input)["goal_relevant"]:
        return ""
    lowered = normalize_text(user_input + "\n" + "\n".join(goal_context or []))
    if "skip gym" in lowered:
        return "Skipping today reduces weekly fitness consistency and makes restarting harder tomorrow."
    if any(word in lowered for word in ("study", "exam", "biotech", "career")):
        return "The best next move is the one that compounds into exam readiness and career clarity over the next few months."
    if any(word in lowered for word in ("money", "spend", "buy")):
        return "A strong decision here should still look good a few weeks from now, not just feel good today."
    return ""


def detect_intent_override(user_input, goal_context):
    lowered = normalize_text(user_input + "\n" + "\n".join(goal_context or []))
    risky_markers = ("shortcut to pass exam", "shortcuts to pass exam", "cheat", "skip gym", "ignore workout")
    return any(marker in lowered for marker in risky_markers)


def handle_fast_response(user_input, active_goal_context, attention, answer_mode="auto", complexity="simple"):
    control = normalize_control_mode(answer_mode)
    identity_context = render_identity_context()
    prompt = f"""
Goal context:
{chr(10).join(active_goal_context or []) or 'None'}

Identity context:
{chr(10).join(identity_context or []) or 'None'}

User request:
{user_input}
""".strip()
    extra_system_prompt = """
Give a sharp direct answer.
Keep it compact unless the user clearly needs more.
If the request is simple, do not overthink or over-explain.
""".strip()
    extra_system_prompt = merge_system_prompts(extra_system_prompt, build_response_style_prompt(control))
    answer, provider, _ = ask_friday_llm_mode(prompt, mode={"depth_mode": "quick", "response_style": control["response_style"], "force_fast": True, "safe_mode": control["safe_mode"], "ask_better_question": control["ask_better_question"]}, extra_system_prompt=extra_system_prompt)
    final_text = (answer or "").strip() or build_minimal_answer(user_input)
    future_step = build_future_prediction(user_input, final_text, active_goal_context)
    if future_step and "next likely step:" not in final_text.lower():
        final_text += "\n\nNext likely step: " + future_step

    confidence = clamp_confidence(0.74 + float(attention.get("priority_score") or 0.0) * 0.12)
    metric_bundle = estimate_metric_bundle(user_input, final_text, confidence, response_type="answer")
    log_response_metric(user_input, "answer", confidence, **metric_bundle)
    write_debug_snapshot(
        {
            "mode": control,
            "complexity": complexity,
            "response_type": "answer",
            "confidence": format_confidence_percent(confidence),
            "draft_a": final_text,
            "draft_b": "",
            "critic": "Fast path used to avoid full multi-pass reasoning.",
            "finalizer_decision": f"Priority {attention.get('priority_level', 'low')} -> compact reply via {provider or 'quick route'}.",
            "final_answer": final_text,
        }
    )
    learn_rules_from_turn(user_input, final_text, confidence)
    return final_text


def maybe_ask_clarifying_question(user_input, attention, complexity, control_mode=None):
    control = normalize_control_mode(control_mode)
    if control["force_fast"] or control["safe_mode"]:
        return ""
    lowered = normalize_text(user_input)
    if attention.get("priority_level") == "low":
        return ""
    if any(phrase in lowered for phrase in ("biotech or nursing", "which is better", "what should i choose", "should i choose", "x or y", "vs")):
        return "Before I answer, what matters more here: salary, abroad chances, or job stability?"
    if complexity in {"complex", "critical"} and any(word in lowered for word in ("should i", "choose", "plan", "roadmap")):
        return "Before I lock in advice, what matters most here: speed, safety, or long-term upside?"
    return ""


def detect_primary_topic(user_input):
    lowered = normalize_text(user_input)
    for topic in ("biotech", "career", "nursing", "study", "exam", "fitness", "diet", "python", "project"):
        if topic in lowered:
            return topic
    return ""


def join_notes(*notes):
    merged = []
    for note in notes:
        clean = (note or "").strip()
        if clean and clean not in merged:
            merged.append(clean)
    return "\n\n".join(merged)


def merge_system_prompts(*parts):
    merged = []
    for part in parts:
        clean = (part or "").strip()
        if clean:
            merged.append(clean)
    return "\n\n".join(merged)


def build_minimal_answer(user_input):
    lowered = normalize_text(user_input)
    if "hi" in lowered or "hello" in lowered or "hey" in lowered:
        return "Hey."
    if "?" in lowered:
        return "Here’s the short version: it depends on your goal, but I can refine it if you want."
    return "Here’s the short answer based on what you asked."


def ensure_response_guarantee(answer_text, user_input, control_mode=None):
    clean = (answer_text or "").strip()
    if not clean or clean.lower() == "i couldn't complete that request.":
        clean = build_minimal_answer(user_input)
    if normalize_control_mode(control_mode)["response_style"] == "one_line":
        clean = " ".join(clean.split())
    return clean


def analyze_query_profile(user_input):
    lowered = normalize_text(user_input)
    hobby_markers = ("hobby", "hobbies", "like", "play games", "games", "favorite", "what do i enjoy")
    goal_markers = ("goal", "plan", "roadmap", "study", "career", "exam", "fitness", "diet", "gym", "abroad", "job")
    profile_markers = ("about me", "my hobbies", "tell my hobbies", "what do you know about me", "my favorite", "i like")

    hobby_relevant = any(marker in lowered for marker in hobby_markers)
    goal_relevant = any(marker in lowered for marker in goal_markers)
    profile_relevant = hobby_relevant or any(marker in lowered for marker in profile_markers)

    return {
        "hobby_relevant": hobby_relevant,
        "goal_relevant": goal_relevant,
        "profile_relevant": profile_relevant,
        "allow_life_context": goal_relevant,
        "allow_identity_context": profile_relevant or goal_relevant,
        "allow_session_context": not hobby_relevant or goal_relevant,
        "allow_deep_memory": not hobby_relevant,
    }

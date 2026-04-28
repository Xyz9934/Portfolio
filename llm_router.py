from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError, as_completed
from multiprocessing import Process, Queue
from time import perf_counter

from config import (
    GEMINI_API_KEY,
    GEMINI_API_KEY_BACKUP,
    GEMINI_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_DEEP_MODEL,
    OLLAMA_ENABLED,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_MODEL,
    OLLAMA_QUICK_MODEL,
    OPENAI_API_KEY,
    OPENAI_CHAT_MODEL,
    PREFER_OFFLINE_BRAIN,
)
from assistant_memory import load_profile
from control_profile import build_response_style_prompt, normalize_control_mode
from evolution_engine import get_prompt_rule_context
from fast_cache import get_cached_response, put_cached_response
from system_health import record_health_event, should_force_safe_mode
from ultra_intelligence import parse_json_object


MODEL_TIMEOUT_SECONDS = 6
OLLAMA_TIMEOUT_SECONDS = 18

FRIDAY_PERSONALITY_PROMPT = """
You are FRIDAY, a smart personal AI assistant inspired by JARVIS.

Style:
- Warm, sharp, helpful, and confident
- Natural and human, never robotic
- Brief unless more detail is clearly useful
- Slight personality is good, but stay practical
- In casual chat, you may use 1 fitting emoji when it feels natural
- Do not overuse emojis, and avoid emojis in serious or technical answers

Behavior:
- Think before answering
- Prefer actionable answers over vague explanations
- Use the user's memory/context when relevant
- If context is insufficient, say so honestly
- Do not invent facts
""".strip()


def ask_friday_llm(user_prompt, extra_system_prompt="", include_debug=False, control_mode=None):
    control = normalize_control_mode(control_mode)
    system_prompt = build_system_prompt(user_prompt, extra_system_prompt, control_mode=control)
    debug_lines = []
    if should_force_safe_mode():
        control["safe_mode"] = True
        control["depth_mode"] = "safe"
    cached = get_cached_response(user_prompt, control_mode=control)
    if cached:
        return cached, "Fast cache", ["Cache hit"] if include_debug else []

    ollama_strategy = choose_ollama_strategy(user_prompt, system_prompt, preferred="quick", control_mode=control)

    for provider_name, provider, provider_timeout in build_provider_chain(system_prompt, ollama_strategy=ollama_strategy):
        if include_debug:
            debug_lines.append(f"Trying {provider_name}...")
        answer = call_with_timeout(provider, user_prompt, timeout_seconds=provider_timeout)
        if answer:
            put_cached_response(user_prompt, answer, control_mode=control)
            if include_debug:
                return answer, provider_name, debug_lines
            return answer, provider_name, []
        if include_debug:
            debug_lines.append(f"{provider_name} unavailable or failed.")

    return "", "", debug_lines


def ask_friday_llm_mode(user_prompt, mode="auto", extra_system_prompt="", include_debug=False):
    normalized_mode = (mode or "auto").strip().lower() if isinstance(mode, str) else "auto"
    control = normalize_control_mode(mode if isinstance(mode, dict) else mode)
    if normalized_mode == "quick_ollama":
        return ask_ollama_mode(user_prompt, strategy="quick", extra_system_prompt=extra_system_prompt, include_debug=include_debug, control_mode=control)
    if normalized_mode == "deep_ollama":
        return ask_ollama_mode(user_prompt, strategy="deep", extra_system_prompt=extra_system_prompt, include_debug=include_debug, control_mode=control)
    if normalized_mode == "critical":
        return ask_ollama_mode(user_prompt, strategy="critical", extra_system_prompt=extra_system_prompt, include_debug=include_debug, control_mode=control)
    if isinstance(mode, dict):
        if control["safe_mode"] or control["depth_mode"] in {"quick", "safe"}:
            return ask_ollama_mode(user_prompt, strategy="quick", extra_system_prompt=extra_system_prompt, include_debug=include_debug, control_mode=control)
        if control["depth_mode"] == "deep":
            return ask_ollama_mode(user_prompt, strategy="deep", extra_system_prompt=extra_system_prompt, include_debug=include_debug, control_mode=control)
    return ask_friday_llm(user_prompt, extra_system_prompt=extra_system_prompt, include_debug=include_debug, control_mode=control)


def ask_ollama_mode(user_prompt, strategy="quick", extra_system_prompt="", include_debug=False, control_mode=None):
    control = normalize_control_mode(control_mode)
    system_prompt = build_system_prompt(user_prompt, extra_system_prompt, control_mode=control)
    debug_lines = []
    provider_name = build_ollama_label(strategy)

    if OLLAMA_ENABLED:
        if include_debug:
            debug_lines.append(f"Trying {provider_name}...")
        answer = call_with_timeout(
            lambda prompt: ask_ollama(prompt, system_prompt, strategy=strategy),
            user_prompt,
            timeout_seconds=OLLAMA_TIMEOUT_SECONDS,
        )
        if answer:
            put_cached_response(user_prompt, answer, control_mode=control)
            if include_debug:
                return answer, provider_name, debug_lines
            return answer, provider_name, []
        if include_debug:
            debug_lines.append(f"{provider_name} unavailable or failed.")

    if strategy == "quick":
        return "", "", debug_lines

    fallback = ask_friday_llm_ultra if strategy in {"deep", "critical"} else ask_friday_llm
    answer, fallback_provider, fallback_debug = fallback(
        user_prompt,
        extra_system_prompt=extra_system_prompt,
        include_debug=include_debug,
        control_mode=control,
    )
    if answer:
        provider_label = fallback_provider or ("deep fallback" if strategy in {"deep", "critical"} else "quick fallback")
        if include_debug:
            return answer, provider_label, debug_lines + fallback_debug
        return answer, provider_label, []
    return "", "", debug_lines + fallback_debug if include_debug else []


def ask_friday_llm_ultra(user_prompt, extra_system_prompt="", include_debug=False, control_mode=None):
    control = normalize_control_mode(control_mode)
    if control["safe_mode"]:
        return ask_ollama_mode(user_prompt, strategy="quick", extra_system_prompt=extra_system_prompt, include_debug=include_debug, control_mode=control)
    system_prompt = build_system_prompt(user_prompt, extra_system_prompt, control_mode=control)
    debug_lines = []
    ollama_strategy = choose_ollama_strategy(user_prompt, system_prompt, preferred="critical", control_mode=control)
    provider_chain = build_provider_chain(system_prompt, ollama_strategy=ollama_strategy)
    candidates = []

    if not provider_chain:
        return "", "", debug_lines

    with ThreadPoolExecutor(max_workers=max(1, min(3, len(provider_chain)))) as executor:
        futures = {}
        for provider_name, provider, provider_timeout in provider_chain[:3]:
            futures[executor.submit(call_with_timeout, provider, user_prompt, timeout_seconds=provider_timeout)] = provider_name
        try:
            for future in as_completed(futures, timeout=OLLAMA_TIMEOUT_SECONDS + 2):
                provider_name = futures[future]
                try:
                    answer = future.result()
                except Exception:
                    answer = None
                if include_debug:
                    debug_lines.append(f"{provider_name}: {'ok' if answer else 'failed'}")
                if answer:
                    candidates.append({"provider": provider_name, "answer": answer.strip()})
        except Exception:
            pass

    if not candidates:
        return "", "", debug_lines

    if len(candidates) == 1:
        candidate = candidates[0]
        improved = meta_review_answer(user_prompt, candidate["answer"], provider_chain)
        final_answer = improved or candidate["answer"]
        return final_answer, candidate["provider"] + " + meta-review", debug_lines

    fused = synthesize_candidates(user_prompt, candidates, provider_chain)
    if fused:
        return fused, "Multi-brain fusion", debug_lines

    best = max(candidates, key=lambda item: len(item["answer"]))
    improved = meta_review_answer(user_prompt, best["answer"], provider_chain)
    return improved or best["answer"], best["provider"] + " + meta-review", debug_lines


def build_system_prompt(user_prompt="", extra_system_prompt="", control_mode=None):
    system_prompt = FRIDAY_PERSONALITY_PROMPT
    style_prompt = build_style_prompt(user_prompt)
    if style_prompt:
        system_prompt += "\n\n" + style_prompt
    rules_prompt = get_prompt_rule_context(limit=6)
    if rules_prompt:
        system_prompt += "\n\n" + rules_prompt
    control_prompt = build_response_style_prompt(control_mode)
    if control_prompt:
        system_prompt += "\n\n" + control_prompt
    if extra_system_prompt:
        if isinstance(extra_system_prompt, str):
            system_prompt += "\n\n" + extra_system_prompt.strip()
    return system_prompt


def build_style_prompt(user_prompt=""):
    profile = load_profile()
    preferences = profile.get("preferences", {})
    instructions = []
    context_name = detect_prompt_context(user_prompt)

    defaults = {
        "work": {"brevity": "", "clarity": "simpler explanations", "tone": "professional tone"},
        "goal": {"brevity": "", "clarity": "simpler explanations", "tone": ""},
        "casual": {"brevity": "", "clarity": "", "tone": "casual tone"},
    }
    active = dict(defaults.get(context_name, defaults["casual"]))

    for category in ("brevity", "clarity", "tone"):
        context_value = _get_preference_value(preferences, f"response style {context_name} {category}")
        global_value = _get_preference_value(preferences, f"response style {category}")
        if context_value:
            active[category] = context_value
        if global_value:
            active[category] = global_value

    brevity = active.get("brevity", "")
    clarity = active.get("clarity", "")
    tone = active.get("tone", "")

    if brevity == "shorter answers":
        instructions.append("Prefer short, compact answers unless extra detail is necessary.")
    if clarity == "simpler explanations":
        instructions.append("Use simpler language and avoid unnecessarily complex phrasing.")
    if tone == "professional tone":
        instructions.append("Use a professional, neutral tone and avoid flirtiness.")
    elif tone == "less flirty tone":
        instructions.append("Avoid flirtiness and keep the tone warm but restrained.")
    elif tone == "casual tone":
        instructions.append("Use a casual, relaxed tone.")

    if not instructions:
        return ""
    return f"Saved response style preferences for {context_name} context:\n- " + "\n- ".join(instructions)


def _get_preference_value(preferences, key):
    item = preferences.get(key)
    if isinstance(item, dict):
        return item.get("value", "")
    return ""


def detect_prompt_context(user_prompt):
    lowered = (user_prompt or "").lower()
    if any(word in lowered for word in ("code", "debug", "python", "bug", "app", "script", "deploy", "project")):
        return "work"
    if any(word in lowered for word in ("plan", "goal", "study", "career", "roadmap", "gym", "muscle")):
        return "goal"
    return "casual"


def assess_request_complexity(user_prompt, system_prompt=""):
    prompt = f"{system_prompt}\n{user_prompt}".lower()
    critical_markers = ("step by step", "analyze", "debate", "architecture", "refactor", "tradeoff", "compare", "challenge assumption")
    complex_markers = ("debug", "why", "how does", "plan", "roadmap", "strategy", "future impact", "long-term")

    if len(prompt) > 3200 or prompt.count("\n") >= 24:
        return "critical"
    if any(marker in prompt for marker in critical_markers):
        return "critical"
    if len(prompt) > 1400 or prompt.count("\n") >= 12:
        return "complex"
    if any(marker in prompt for marker in complex_markers):
        return "complex"
    if len(prompt.split()) > 55:
        return "medium"
    return "simple"


def choose_ollama_strategy(user_prompt, system_prompt="", preferred="quick", control_mode=None):
    control = normalize_control_mode(control_mode)
    forced_strategy = control.get("ollama_strategy", "")
    if forced_strategy in {"quick", "deep"}:
        return forced_strategy
    if control["safe_mode"] or control["depth_mode"] in {"quick", "safe"} or control["force_fast"]:
        return "quick"
    if control["depth_mode"] == "deep":
        return "deep"
    complexity = assess_request_complexity(user_prompt, system_prompt)
    if preferred == "critical":
        return "deep"
    if preferred == "deep":
        return "deep"
    if complexity == "critical":
        return "deep"
    return "quick"


def build_provider_chain(system_prompt, ollama_strategy="quick"):
    providers = []
    ollama_label = build_ollama_label(ollama_strategy)
    if OLLAMA_ENABLED and PREFER_OFFLINE_BRAIN:
        providers.append((ollama_label, lambda prompt: ask_ollama(prompt, system_prompt, strategy=ollama_strategy), OLLAMA_TIMEOUT_SECONDS))
    if GEMINI_API_KEY:
        providers.append(("Gemini primary", lambda prompt: ask_gemini(prompt, system_prompt, GEMINI_API_KEY), MODEL_TIMEOUT_SECONDS))
    if GEMINI_API_KEY_BACKUP:
        providers.append(("Gemini backup", lambda prompt: ask_gemini(prompt, system_prompt, GEMINI_API_KEY_BACKUP), MODEL_TIMEOUT_SECONDS))
    if OPENAI_API_KEY:
        providers.append(("GPT backup", lambda prompt: ask_openai(prompt, system_prompt), MODEL_TIMEOUT_SECONDS))
    if OLLAMA_ENABLED and not PREFER_OFFLINE_BRAIN:
        providers.append((ollama_label, lambda prompt: ask_ollama(prompt, system_prompt, strategy=ollama_strategy), OLLAMA_TIMEOUT_SECONDS))
    return providers


def build_ollama_label(strategy):
    if strategy in {"deep", "critical"}:
        return f"Ollama deep ({OLLAMA_DEEP_MODEL})"
    if strategy == "quick":
        return f"Ollama quick ({OLLAMA_QUICK_MODEL})"
    return "Ollama auto-switch"


def ask_gemini(user_prompt, system_prompt, api_key):
    if not api_key:
        return None

    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(f"{system_prompt}\n\nUser request:\n{user_prompt}")
        return (response.text or "").strip()
    except Exception:
        return None


def ask_openai(user_prompt, system_prompt):
    if not OPENAI_API_KEY:
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=OPENAI_API_KEY, timeout=MODEL_TIMEOUT_SECONDS)
        response = client.chat.completions.create(
            model=OPENAI_CHAT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return (response.choices[0].message.content or "").strip()
    except Exception:
        return None


def ask_ollama(user_prompt, system_prompt, strategy="quick"):
    if not OLLAMA_ENABLED:
        return None

    started = perf_counter()
    try:
        model_name = select_ollama_model(user_prompt, system_prompt, strategy=strategy)
        answer = _ask_ollama_in_process(user_prompt, system_prompt, model_name, timeout_seconds=OLLAMA_TIMEOUT_SECONDS)
        record_health_event("ollama", latency_ms=int((perf_counter() - started) * 1000), ok=bool(answer), note=strategy)
        return answer
    except Exception:
        record_health_event("ollama", latency_ms=int((perf_counter() - started) * 1000), ok=False, note=strategy)
        return None


def select_ollama_model(user_prompt, system_prompt="", strategy="quick"):
    if strategy in {"deep", "critical"}:
        return OLLAMA_DEEP_MODEL or OLLAMA_MODEL
    if strategy == "quick":
        return OLLAMA_QUICK_MODEL or OLLAMA_MODEL

    complexity = assess_request_complexity(user_prompt, system_prompt)
    if complexity in {"complex", "critical"}:
        return OLLAMA_DEEP_MODEL or OLLAMA_MODEL
    return OLLAMA_QUICK_MODEL or OLLAMA_MODEL


def synthesize_candidates(user_prompt, candidates, provider_chain):
    fusion_prompt = build_fusion_prompt(user_prompt, candidates)
    for _, provider, provider_timeout in provider_chain:
        answer = call_with_timeout(provider, fusion_prompt, timeout_seconds=provider_timeout)
        if not answer:
            continue
        parsed = parse_json_object(answer)
        merged = (parsed.get("merged_answer") or "").strip()
        if merged:
            return merged
        return answer.strip()
    return ""


def meta_review_answer(user_prompt, draft_answer, provider_chain):
    review_prompt = f"""
Review this draft answer for the user request.
Return strict JSON with keys:
- critique
- improved_answer

User request:
{user_prompt}

Draft answer:
{draft_answer}
""".strip()
    for _, provider, provider_timeout in provider_chain:
        answer = call_with_timeout(provider, review_prompt, timeout_seconds=provider_timeout)
        if not answer:
            continue
        parsed = parse_json_object(answer)
        improved = (parsed.get("improved_answer") or "").strip()
        if improved:
            return improved
    return ""


def build_fusion_prompt(user_prompt, candidates):
    candidate_lines = []
    for index, item in enumerate(candidates, start=1):
        candidate_lines.append(f"Candidate {index} from {item['provider']}:\n{item['answer']}")
    joined = "\n\n".join(candidate_lines)
    return f"""
You are FRIDAY's meta-reasoning engine.
Compare the candidate answers below.
Choose the strongest ideas, remove weak claims, and produce one improved final answer.
Return strict JSON with keys:
- reasoning_summary
- merged_answer

User request:
{user_prompt}

Candidates:
{joined}
""".strip()


def call_with_timeout(func, *args, timeout_seconds=MODEL_TIMEOUT_SECONDS):
    executor = ThreadPoolExecutor(max_workers=1)
    future = None
    try:
        future = executor.submit(func, *args)
        return future.result(timeout=timeout_seconds)
    except FutureTimeoutError:
        return None
    except Exception:
        return None
    finally:
        if future is not None:
            try:
                future.cancel()
            except Exception:
                pass
        executor.shutdown(wait=False, cancel_futures=True)


def _ollama_worker(queue, base_url, model_name, full_prompt, keep_alive, timeout_seconds):
    try:
        import requests

        response = requests.post(
            f"{base_url.rstrip('/')}/api/generate",
            json={
                "model": model_name,
                "prompt": full_prompt,
                "stream": False,
                "keep_alive": keep_alive,
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        queue.put((data.get("response") or "").strip())
    except Exception:
        queue.put("")


def _ask_ollama_in_process(user_prompt, system_prompt, model_name, timeout_seconds=OLLAMA_TIMEOUT_SECONDS):
    queue = Queue(maxsize=1)
    process = Process(
        target=_ollama_worker,
        args=(
            queue,
            OLLAMA_BASE_URL,
            model_name,
            f"{system_prompt}\n\nUser request:\n{user_prompt}",
            OLLAMA_KEEP_ALIVE,
            timeout_seconds,
        ),
    )
    process.start()
    process.join(timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join(1)
        return None
    try:
        return queue.get_nowait() or None
    except Exception:
        return None

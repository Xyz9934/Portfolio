import os
import time

from llm_router import ask_friday_llm


def can_handle_code_request(text):
    normalized = (text or "").strip().lower()
    triggers = (
        "code:",
        "write code",
        "generate code",
        "create code",
        "build a script",
        "make a script",
        "fix this code",
        "debug this code",
        "write a python",
        "write a java",
        "write a javascript",
        "write a c++",
    )
    return any(trigger in normalized for trigger in triggers)


def run_code_mode(user_request, workspace_dir):
    started_at = time.perf_counter()
    context = build_workspace_context(workspace_dir)
    debug_lines = ["Preparing coding context..."]
    prompt = f"""
Workspace context:
{context}

User request:
{user_request}
"""

    extra_system_prompt = """
You are in FRIDAY Auto-Coding Mode.
Give direct, useful coding help with runnable code when appropriate.
Prefer complete code blocks over fragments.
If the request sounds like a bug fix, explain the issue briefly and then provide corrected code.
""".strip()

    answer, provider_name, provider_debug = ask_friday_llm(
        prompt,
        extra_system_prompt=extra_system_prompt,
        include_debug=True,
    )
    if answer:
        elapsed = time.perf_counter() - started_at
        debug_lines.extend(provider_debug)
        return "[AUTO-CODING MODE]\n" + "\n".join(debug_lines) + f"\n{provider_name} responded in {elapsed:.2f}s.\n\n" + answer

    elapsed = time.perf_counter() - started_at
    debug_lines.extend(provider_debug)
    return (
        "[AUTO-CODING MODE]\n"
        + "\n".join(debug_lines)
        + f"\nNo coding model responded in {elapsed:.2f}s.\n\n"
        + "Auto-coding mode is available, but no coding model is reachable right now."
    )


def build_workspace_context(workspace_dir):
    try:
        entries = []
        for name in sorted(os.listdir(workspace_dir))[:40]:
            path = os.path.join(workspace_dir, name)
            entries.append(f"{'[DIR]' if os.path.isdir(path) else '[FILE]'} {name}")
        return "\n".join(entries)
    except Exception:
        return "Workspace listing unavailable."

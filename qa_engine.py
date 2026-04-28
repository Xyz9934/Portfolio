def ask_friday(question, answer_mode="auto"):
    try:
        from thinking_engine import run_friday_request

        return run_friday_request(question, answer_mode=answer_mode)
    except Exception:
        try:
            from local_ai_core import ask_ai

            return ask_ai(question)
        except Exception as exc:
            return f"System error occurred: {exc}"

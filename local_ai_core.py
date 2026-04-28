from config import OLLAMA_ENABLED, OLLAMA_MODEL
from llm_router import ask_friday_llm
from search_brain import search_web


def ask_ai(prompt, context=""):
    try:
        offline_system_prompt = """
You are FRIDAY's offline brain.
Answer clearly and intelligently using only the provided context and your local model knowledge.
If the user asks for something current that you cannot verify offline, say that plainly.
""".strip()
        query = f"{context}\n\nUser: {prompt}".strip()

        answer, provider_name, _ = ask_friday_llm(query, extra_system_prompt=offline_system_prompt, include_debug=True)
        if answer:
            return answer

        result = search_web(query)
        if result:
            if OLLAMA_ENABLED:
                return f"Offline brain `{OLLAMA_MODEL}` was unavailable, so I used fallback search.\n\n{result}"
            return result
        return "FRIDAY could not find information."
    except Exception as e:
        return f"AI Core Error: {e}"

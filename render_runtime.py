from config import (
    API_ENABLE_LIVE_SEARCH,
    API_ENABLE_PDF_INGEST,
    CLOUD_SAFE_MODE,
    remote_knowledge_available,
)
from llm_router import ask_friday_llm_mode


def answer_with_render_runtime(question, answer_mode="auto"):
    text = (question or "").strip()
    if not text:
        return "Ask me anything."

    if API_ENABLE_LIVE_SEARCH:
        try:
            from internet_brain import can_handle_live_query, handle_live_query

            if can_handle_live_query(text):
                live_answer = handle_live_query(text)
                if live_answer:
                    return live_answer
        except Exception:
            pass

    system_prompt = build_render_system_prompt()
    answer, provider, _ = ask_friday_llm_mode(
        text,
        mode=answer_mode,
        extra_system_prompt=system_prompt,
    )
    if answer:
        return answer

    if provider:
        return f"FRIDAY could not produce a final response. Last provider tried: {provider}."
    return "FRIDAY could not produce a response right now."


def ingest_pdf_for_api(path):
    if not API_ENABLE_PDF_INGEST:
        raise RuntimeError(
            "PDF ingest is disabled for this deployment. Set API_ENABLE_PDF_INGEST=true only if the required memory services are configured."
        )
    if CLOUD_SAFE_MODE and not remote_knowledge_available():
        raise RuntimeError(
            "PDF ingest requires a persistent remote knowledge backend in cloud mode. Configure Pinecone, Firebase, or Firestore first."
        )

    from semantic_brain import ingest_pdf

    return ingest_pdf(path)


def build_render_system_prompt():
    lines = [
        "You are FRIDAY running as a cloud API.",
        "Do not reference local device controls, microphones, on-screen UI, or desktop-only capabilities unless the user explicitly asks whether they exist.",
        "If a request depends on a local-only feature, say that this deployed API cannot access the user's device directly.",
    ]
    if CLOUD_SAFE_MODE:
        lines.append("Assume this deployment is stateless and cloud-hosted.")
    return "\n".join(lines)

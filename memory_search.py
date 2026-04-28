from config import FIREBASE_ENABLED, FIRESTORE_ENABLED, PINECONE_API_KEY, PINECONE_INDEX_NAME
from cloud_brain import search_cloud
from cloud_memory import cloud_search
from fast_cache import get_cached_response, put_cached_response
from local_knowledge import search_knowledge
from memory_guard import is_relevant_match
from system_health import should_force_safe_mode

index = None
pinecone_error = None


def get_index():
    global index, pinecone_error

    if index is not None or pinecone_error is not None:
        return index

    try:
        from pinecone import Pinecone

        pc = Pinecone(api_key=PINECONE_API_KEY)
        index = pc.Index(PINECONE_INDEX_NAME)
    except Exception as exc:
        pinecone_error = exc
        index = None

    return index


def search_memory(query_text, vector=None, top_k=5, min_score=0.55):
    top_k = max(1, min(int(top_k or 5), 5))
    min_score = max(0.55, float(min_score or 0.55))
    if should_force_safe_mode():
        top_k = 2
        min_score = 0.7

    cached = get_cached_response(f"memory::{query_text}", control_mode={"depth_mode": "quick", "response_style": "default"})
    if cached:
        return [item for item in cached.split("\n---\n") if item.strip()][:top_k]

    local_matches = search_knowledge(query_text, top_k=top_k)
    if len(local_matches) >= top_k:
        return local_matches[:top_k]
    firebase_matches = []
    firestore_matches = []

    if FIREBASE_ENABLED:
        try:
            firebase_matches = cloud_search(query_text, top_k=top_k)
        except Exception:
            firebase_matches = []

    if FIRESTORE_ENABLED:
        try:
            firestore_matches = search_cloud(query_text, top_k=top_k)
        except Exception:
            firestore_matches = []

    current_index = get_index()

    if current_index is None:
        merged = []
        for item in local_matches + firebase_matches + firestore_matches:
            if item and item not in merged:
                merged.append(item)
        result = merged[:top_k]
        put_cached_response(f"memory::{query_text}", "\n---\n".join(result), control_mode={"depth_mode": "quick", "response_style": "default"})
        return result

    if vector is None:
        try:
            from embeddings_local import embed_text

            vector = embed_text(query_text)
        except Exception:
            merged = []
            for item in local_matches + firebase_matches + firestore_matches:
                if item and item not in merged:
                    merged.append(item)
            result = merged[:top_k]
            put_cached_response(f"memory::{query_text}", "\n---\n".join(result), control_mode={"depth_mode": "quick", "response_style": "default"})
            return result

    results = current_index.query(
        vector=vector,
        top_k=top_k,
        include_metadata=True
    )

    matches = []

    for match in results["matches"]:
        score = match.get("score", 0)
        metadata = match.get("metadata", {})

        text = metadata.get("text")
        if score >= min_score and text and is_relevant_match(query_text, text, strict=True):
            matches.append(text)

    merged = []

    for item in local_matches + firebase_matches + firestore_matches + matches:
        if item and item not in merged:
            merged.append(item)

    result = merged[:top_k]
    put_cached_response(f"memory::{query_text}", "\n---\n".join(result), control_mode={"depth_mode": "quick", "response_style": "default"})
    return result

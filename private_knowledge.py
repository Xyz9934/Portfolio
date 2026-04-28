from local_knowledge import search_knowledge
from memory_search import search_memory


def query_private_knowledge(query, limit=5):
    merged = []
    for item in search_memory(query, top_k=limit) + search_knowledge(query, top_k=limit):
        if item and item not in merged:
            merged.append(item)
    return merged[:limit]


def render_private_knowledge_context(query, limit=4):
    items = query_private_knowledge(query, limit=limit)
    return [f"Private knowledge - {item}" for item in items]

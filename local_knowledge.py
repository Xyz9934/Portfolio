import json
import os
from memory_guard import is_relevant_match, score_match

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_FILE = os.path.join(BASE_DIR, "knowledge.json")


def load_knowledge():
    try:
        with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return [item for item in data if isinstance(item, str) and item.strip()]
    except Exception:
        pass

    return []


def save_knowledge(items):
    with open(KNOWLEDGE_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def add_knowledge(text):
    if not text or not text.strip():
        return

    items = load_knowledge()
    cleaned = text.strip()

    if cleaned not in items:
        items.append(cleaned)
        save_knowledge(items)


def search_knowledge(query, top_k=5):
    scored = []

    for item in load_knowledge():
        if not is_relevant_match(query, item, strict=True):
            continue

        score, overlap, _ = score_match(query, item)
        exact_phrase_bonus = 1 if query.lower() in item.lower() else 0
        scored.append((exact_phrase_bonus, score, overlap, item))

    scored.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    return [item for _, _, _, item in scored[:top_k]]

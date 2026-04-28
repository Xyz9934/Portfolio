import math
import re


STOP_WORDS = {
    "a", "an", "the", "is", "am", "are", "was", "were", "be", "been", "being",
    "who", "what", "when", "where", "why", "how", "tell", "me", "about", "please",
    "do", "does", "did", "of", "for", "to", "in", "on", "at", "from", "with",
    "and", "or", "my", "your", "our", "their", "this", "that", "these", "those",
    "latest", "today", "todays", "now", "current", "explain",
    "ms", "mr", "mrs", "miss",
}


def tokenize(text):
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def keyword_tokens(text):
    tokens = []
    for token in tokenize(text):
        if token in STOP_WORDS:
            continue
        if len(token) == 1 and not token.isdigit():
            continue
        tokens.append(token)
    return tokens


def score_match(query, candidate):
    query_keywords = set(keyword_tokens(query))
    candidate_tokens = set(tokenize(candidate))

    if not query_keywords:
        return 0.0, 0, 0

    overlap = len(query_keywords & candidate_tokens)
    ratio = overlap / max(len(query_keywords), 1)
    phrase_bonus = 0.35 if normalize(query) in normalize(candidate) else 0.0
    return ratio + phrase_bonus, overlap, len(query_keywords)


def is_relevant_match(query, candidate, strict=True):
    score, overlap, keyword_count = score_match(query, candidate)
    if keyword_count == 0:
        return False

    required_overlap = 1 if keyword_count == 1 else min(keyword_count, max(2, math.ceil(keyword_count * 0.5)))
    if strict:
        return overlap >= required_overlap and score >= 0.6

    return overlap >= max(1, min(required_overlap, 2)) and score >= 0.45


def normalize(text):
    return re.sub(r"\s+", " ", (text or "").strip().lower())

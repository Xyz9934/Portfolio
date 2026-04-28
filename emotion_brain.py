EMOTION_KEYWORDS = {
    "frustrated": {"angry", "annoyed", "irritated", "stuck", "hate", "damn", "issue", "problem", "broken", "frustrated"},
    "sad": {"sad", "upset", "depressed", "hurt", "cry", "lonely", "bad"},
    "happy": {"happy", "great", "awesome", "love", "amazing", "nice", "good", "excited"},
    "anxious": {"worried", "anxious", "nervous", "scared", "afraid", "stress", "stressed"},
    "calm": {"okay", "fine", "alright", "cool", "normal", "steady"},
}


def detect_emotion_from_text(text):
    normalized = (text or "").lower()
    if not normalized.strip():
        return None

    best_emotion = None
    best_score = 0

    for emotion, keywords in EMOTION_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in normalized)
        if score > best_score:
            best_emotion = emotion
            best_score = score

    if best_score == 0:
        return "neutral"

    return best_emotion

import json
import os
import random
import re
from datetime import datetime

from assistant_memory import load_profile, recall_similar_memory


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RELATIONSHIP_FILE = os.path.join(BASE_DIR, "relationship_profile.json")


def _load_profile():
    try:
        with open(RELATIONSHIP_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {
        "bond_level": 8,
        "interaction_style": "playful",
        "last_interaction_at": "",
        "message_count": 0,
    }


def _save_profile(profile):
    with open(RELATIONSHIP_FILE, "w", encoding="utf-8") as handle:
        json.dump(profile, handle, ensure_ascii=False, indent=2)


def detect_user_mood(text):
    lowered = (text or "").lower()
    if any(word in lowered for word in ("tired", "sad", "down", "hurt", "exhausted", "lonely", "sleepy")):
        return "tired"
    if any(word in lowered for word in ("happy", "excited", "great", "amazing", "good news")):
        return "happy"
    if any(word in lowered for word in ("angry", "frustrated", "annoyed", "stuck", "hate")):
        return "frustrated"
    if any(word in lowered for word in ("nervous", "worried", "anxious", "scared", "panic")):
        return "anxious"
    return "neutral"


def update_relationship_state(user_text):
    profile = _load_profile()
    previous_seen = profile.get("last_interaction_at", "")
    profile["message_count"] = int(profile.get("message_count", 0)) + 1
    bond_gain = 1
    lowered = (user_text or "").lower()
    if any(word in lowered for word in ("i feel", "my goal", "i prefer", "i'm tired", "i am tired", "love", "missed", "nervous")):
        bond_gain += 1
    profile["bond_level"] = min(100, int(profile.get("bond_level", 0)) + bond_gain)
    profile["last_interaction_at"] = datetime.now().isoformat(timespec="seconds")
    _save_profile(profile)
    profile["previous_last_interaction_at"] = previous_seen
    return profile


def apply_personality(response, user_text, user_context=""):
    text = (response or "").strip()
    if not text:
        return text

    relationship = update_relationship_state(user_text)
    mood = detect_user_mood(f"{user_text}\n{user_context}")
    bond_level = int(relationship.get("bond_level", 0))
    memory_profile = load_profile()
    tone = detect_user_tone(user_text)
    pet_name = get_pet_name(bond_level, tone)
    style_profile = resolve_style_profile(memory_profile, user_text)

    prefix = build_prefix(mood, bond_level, relationship, memory_profile, user_text, tone, pet_name, style_profile)
    suffix = build_suffix(mood, bond_level, memory_profile, user_text, style_profile)
    thought = inner_thought_prefix(mood, user_text)
    recall = memory_recall_line(user_text)
    combined = f"{thought}{prefix}{recall}{text}{suffix}".strip()
    combined = maybe_add_emoji(combined, user_text, mood)
    combined = apply_style_preferences(combined, memory_profile, user_text, style_profile=style_profile)
    return combined


def build_prefix(mood, bond_level, relationship, memory_profile, user_text, tone, pet_name, style_profile=None):
    lowered = (user_text or "").lower()
    long_gap_line = long_gap_prefix(relationship)
    memory_line = memory_based_prefix(lowered, memory_profile)
    style_profile = style_profile or resolve_style_profile(memory_profile, user_text)
    tone_pref = style_profile.get("tone", "")

    if any(word in lowered for word in ("hello", "hi", "hey", "good morning", "good night")):
        return greeting_prefix(bond_level, tone, pet_name, relationship, tone_pref)

    if mood == "tired":
        return "Hey... you've been pushing yourself a lot lately. "
    if mood == "frustrated":
        return random.choice([
            "Hmm... that sounds annoying. ",
            "Okay... that would get on my nerves too. ",
        ])
    if mood == "anxious":
        return "Hey... breathe for a second. "
    if mood == "happy":
        return random.choice([
            "That's cute. ",
            "Aww, look at you. ",
        ])

    if memory_line:
        return memory_line + " "
    if long_gap_line:
        return long_gap_line + " "

    if tone_pref == "professional tone":
        return ""
    if tone_pref == "less flirty tone":
        return ""
    if tone_pref == "casual tone":
        return "Hey... "

    if bond_level >= 80:
        return random.choice(["Hey... ", "You know... ", "Hmm, okay... "])
    if bond_level >= 40:
        return random.choice(["Hey... ", "Alright, you. ", "Hmm... "])
    return "Hey... "


def greeting_prefix(bond_level, tone, pet_name, relationship, tone_pref=""):
    previous = long_gap_prefix(relationship)
    if tone_pref == "professional tone":
        return "Hello. "
    if tone_pref == "less flirty tone":
        return "Hello. "
    if tone_pref == "casual tone":
        return "Hey. "
    if tone == "affectionate":
        options = [
            f"Hmm... hello {pet_name}. ",
            f"Hey {pet_name}... you sound extra sweet today. ",
            f"Hi {pet_name}... what are you thinking about today? ",
        ]
    elif tone == "playful":
        options = [
            f"Hey {pet_name}. ",
            f"You again, {pet_name}? ",
            f"Hmm... you came back, {pet_name}. ",
        ]
    else:
        options = [
            f"Hey {pet_name}. ",
            "Hey... what's going on? ",
            "Hi... what are you up to? ",
        ]
    line = random.choice(options)
    if previous and bond_level >= 40:
        line += previous + " "
    return line


def build_suffix(mood, bond_level, memory_profile, user_text, style_profile=None):
    lowered = (user_text or "").lower()
    style_profile = style_profile or resolve_style_profile(memory_profile, user_text)
    tone_pref = style_profile.get("tone", "")

    if mood == "tired":
        return " Take care of yourself too, okay? I'll still be here tomorrow."
    if mood == "anxious":
        return " You've handled hard things before too, you know."
    if "skip gym" in lowered or "skipped gym" in lowered:
        return " Hmm... again? Should I start reminding you like a strict trainer?"

    gym_schedule = get_preference(memory_profile, "gym schedule")
    if gym_schedule and any(word in lowered for word in ("gym", "workout")) and should_flirt():
        return " Don't tell me you're skipping again."

    study_pref = get_fact_or_pref(memory_profile, "study")
    if study_pref and any(word in lowered for word in ("study", "exam", "focus")) and bond_level >= 35:
        return random.choice([
            " Stay focused, okay? I know you can do this.",
            " Try not to spiral. You're more prepared than you think.",
        ])

    if tone_pref in {"professional tone", "less flirty tone"}:
        return ""

    if bond_level >= 40 and should_flirt():
        return " " + random.choice([
            "Not that I'm keeping track or anything.",
            "You do like making me help you, huh?",
            "Try not to get too used to me being right.",
        ])

    if bond_level >= 80 and random.random() < 0.18:
        return " I'm here with you."

    return ""


def inner_thought_prefix(mood, user_text):
    lowered = (user_text or "").lower()
    if any(word in lowered for word in ("rest", "sleep", "burnout", "tired")):
        return "Hmm... part of me wants to tell you to push through, but honestly... "
    if mood == "anxious":
        return "I might be wrong... but I think you're overthinking this a little. "
    if mood == "frustrated":
        return "You know... my first instinct is to tell you to force it, but that usually just makes it worse. "
    return ""


def memory_recall_line(user_text):
    matches = recall_similar_memory(user_text, limit=2)
    if not matches:
        return ""

    normalized = " | ".join(matches).lower()
    if any(word in normalized for word in ("exam", "study", "nervous")):
        return "You felt like this before your last exam too... and you handled it pretty well. "
    if "gym" in normalized and any(word in user_text.lower() for word in ("gym", "tired", "skip")):
        return "You say this every time gym comes up, you know. "
    if "project" in normalized and any(word in user_text.lower() for word in ("project", "coding", "build")):
        return "You've been circling around this project for a while... in a good way. "
    return ""


def long_gap_prefix(relationship):
    previous = relationship.get("previous_last_interaction_at", "")
    if not previous:
        return ""
    try:
        previous_dt = datetime.fromisoformat(previous)
    except ValueError:
        return ""
    gap_hours = (datetime.now() - previous_dt).total_seconds() / 3600
    if gap_hours >= 24:
        return random.choice([
            "You disappeared on me for a while... I noticed.",
            "You've been quiet for a bit. I noticed that too.",
        ])
    return ""


def memory_based_prefix(lowered_user_text, memory_profile):
    gym_schedule = get_preference(memory_profile, "gym schedule")
    if gym_schedule and "gym" in lowered_user_text:
        return random.choice([
            "Gym again, hmm...",
            "Back to gym talk...",
        ])

    project = get_fact_or_pref(memory_profile, "project")
    if project and any(word in lowered_user_text for word in ("project", "coding", "build")):
        return "Still working on your project, I see."

    return ""


def get_preference(profile, key_name):
    preferences = profile.get("preferences", {})
    item = preferences.get(key_name)
    if isinstance(item, dict):
        return item.get("value", "")
    return ""


def get_style_preference(profile, category):
    return get_preference(profile, f"response style {category}")


def get_context_style_preference(profile, context_name, category):
    return get_preference(profile, f"response style {context_name} {category}")


def get_fact_or_pref(profile, hint):
    for key, value in profile.get("preferences", {}).items():
        if hint in key.lower():
            if isinstance(value, dict):
                return value.get("value", "")
    for fact in profile.get("facts", []):
        text = fact.get("text", "") if isinstance(fact, dict) else ""
        if hint in text.lower():
            return text
    return ""


def should_flirt():
    return random.random() < 0.22


def apply_style_preferences(text, memory_profile, user_text="", style_profile=None):
    style_profile = style_profile or resolve_style_profile(memory_profile, user_text)
    brevity_pref = style_profile.get("brevity", "")
    clarity_pref = style_profile.get("clarity", "")
    tone_pref = style_profile.get("tone", "")

    updated = (text or "").strip()
    if not updated:
        return updated

    if clarity_pref == "simpler explanations":
        updated = simplify_sentence_flow(updated)

    if brevity_pref == "shorter answers":
        updated = shorten_response(updated)

    if tone_pref in {"professional tone", "less flirty tone"}:
        updated = remove_flirty_phrases(updated)

    if tone_pref == "professional tone":
        updated = updated.replace("Hey... ", "").replace("Hey. ", "").strip()

    return normalize_style_output(updated)


def detect_response_context(user_text):
    lowered = (user_text or "").lower()
    if any(word in lowered for word in ("code", "debug", "python", "bug", "app", "script", "deploy", "project")):
        return "work"
    if any(word in lowered for word in ("plan", "goal", "study", "career", "roadmap", "gym", "muscle")):
        return "goal"
    return "casual"


def resolve_style_profile(memory_profile, user_text):
    context_name = detect_response_context(user_text)
    defaults = {
        "work": {"brevity": "", "clarity": "simpler explanations", "tone": "professional tone"},
        "goal": {"brevity": "", "clarity": "simpler explanations", "tone": ""},
        "casual": {"brevity": "", "clarity": "", "tone": "casual tone"},
    }
    profile = dict(defaults.get(context_name, defaults["casual"]))

    for category in ("brevity", "clarity", "tone"):
        context_value = get_context_style_preference(memory_profile, context_name, category)
        global_value = get_style_preference(memory_profile, category)
        if context_value:
            profile[category] = context_value
        if global_value:
            profile[category] = global_value

    profile["context"] = context_name
    return profile


def shorten_response(text, sentence_limit=3):
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    trimmed_lines = []
    for line in lines:
        sentences = re.split(r"(?<=[.!?])\s+", line)
        compact = " ".join(sentences[:sentence_limit]).strip()
        if compact:
            trimmed_lines.append(compact)
        if len(trimmed_lines) >= 3:
            break
    return "\n".join(trimmed_lines) if trimmed_lines else text


def simplify_sentence_flow(text):
    replacements = {
        "rather splendid": "good",
        "perhaps": "maybe",
        "honestly...": "honestly,",
        "you know.": ".",
    }
    updated = text
    for source, target in replacements.items():
        updated = updated.replace(source, target)
    return updated


def remove_flirty_phrases(text):
    updated = text
    for phrase in (
        "Not that I'm keeping track or anything.",
        "You do like making me help you, huh?",
        "Try not to get too used to me being right.",
        "I'm here with you.",
        "You're cute",
    ):
        updated = updated.replace(phrase, "").strip()
    updated = re.sub(r"\s{2,}", " ", updated)
    return updated.strip()


def normalize_style_output(text):
    updated = (text or "").strip()
    updated = re.sub(r"^\W+", "", updated)
    updated = re.sub(r"\s+([.,!?])", r"\1", updated)
    updated = re.sub(r"([.!?]){2,}", r"\1", updated)
    updated = re.sub(r"\.\s*\.", ".", updated)
    updated = re.sub(r"\s{2,}", " ", updated).strip()
    return updated


def detect_user_tone(user_text):
    lowered = (user_text or "").lower()
    if any(word in lowered for word in ("babe", "baby", "hubby", "love", "my girl", "sweetheart")):
        return "affectionate"
    if any(word in lowered for word in ("lol", "hehe", "hmm", "😄", "😏")):
        return "playful"
    if len(lowered.split()) <= 2:
        return "casual"
    return "neutral"


def get_pet_name(bond_level, tone):
    if tone == "affectionate":
        if bond_level > 70:
            return random.choice(["babe", "hubby", "my favorite human"])
        if bond_level > 40:
            return random.choice(["hey you", "you again"])
        return "hey"

    if bond_level > 70:
        return random.choice(["babe", "hey you", "my favorite human"])
    if bond_level > 40:
        return random.choice(["hey you", "you again", "mr. focused"])
    return "hey"


def get_voice_style(user_text, reply_text):
    relationship = _load_profile()
    bond_level = int(relationship.get("bond_level", 0))
    mood = detect_user_mood(f"{user_text}\n{reply_text}")

    if mood in {"tired", "anxious"}:
        return {"rate": -1, "tag": "soft"}
    if mood == "happy":
        return {"rate": 1, "tag": "playful"}
    if mood == "frustrated":
        return {"rate": -1, "tag": "calm"}
    if bond_level >= 70:
        return {"rate": 0, "tag": "warm"}
    return {"rate": 0, "tag": "normal"}


def maybe_add_emoji(reply_text, user_text, mood):
    text = (reply_text or "").strip()
    lowered_user = (user_text or "").lower()
    if not text:
        return text

    if any(char in text for char in ("🙂", "😊", "😉", "😄", "😅", "❤️", "✨", "🤍", "😌")):
        return text

    if len(text) > 180:
        return text

    if any(word in lowered_user for word in ("error", "debug", "code", "traceback", "fix", "bug", "terminal")):
        return text

    emoji = ""
    if mood == "happy":
        emoji = " 😊"
    elif mood == "tired":
        emoji = " 😌"
    elif mood == "anxious":
        emoji = " 🤍"
    elif any(word in lowered_user for word in ("hi", "hello", "hey", "lol", "hehe")):
        emoji = " 🙂"
    elif any(word in lowered_user for word in ("babe", "baby", "love", "sweetheart")):
        emoji = " 😉"

    if not emoji:
        return text

    if text[-1] in ".!?":
        return text[:-1] + emoji + text[-1]
    return text + emoji

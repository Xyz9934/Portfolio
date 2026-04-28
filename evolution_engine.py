import json
import os
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EVOLUTION_FILE = os.path.join(BASE_DIR, "brain", "evolution_rules.json")


def _now():
    return datetime.now().isoformat(timespec="seconds")


def ensure_evolution_storage():
    os.makedirs(os.path.dirname(EVOLUTION_FILE), exist_ok=True)
    if not os.path.exists(EVOLUTION_FILE):
        with open(EVOLUTION_FILE, "w", encoding="utf-8") as handle:
            json.dump({"rules": []}, handle, ensure_ascii=False, indent=2)


def _load():
    ensure_evolution_storage()
    try:
        with open(EVOLUTION_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            data.setdefault("rules", [])
            return data
    except Exception:
        pass
    return {"rules": []}


def _save(data):
    ensure_evolution_storage()
    with open(EVOLUTION_FILE, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def upsert_rule(rule_key, statement, weight=1.0, source="system"):
    data = _load()
    rules = data.get("rules", [])
    for item in rules:
        if item.get("rule_key") == rule_key:
            item["statement"] = statement
            item["weight"] = float(weight)
            item["source"] = source
            item["updated_at"] = _now()
            _save(data)
            return item
    item = {
        "rule_key": rule_key,
        "statement": statement,
        "weight": float(weight),
        "source": source,
        "updated_at": _now(),
    }
    rules.append(item)
    data["rules"] = rules[-40:]
    _save(data)
    return item


def get_rules(limit=12):
    rules = _load().get("rules", [])
    rules = sorted(rules, key=lambda item: float(item.get("weight") or 0.0), reverse=True)
    return rules[:limit]


def get_rule_context(limit=8):
    context = []
    for item in get_rules(limit=limit):
        statement = (item.get("statement") or "").strip()
        if statement:
            context.append(f"Evolution rule: {statement}")
    return context


def get_prompt_rule_context(limit=6):
    rules = get_rule_context(limit=limit)
    if not rules:
        return ""
    return "Persistent adaptation rules:\n- " + "\n- ".join(line.replace("Evolution rule: ", "") for line in rules)


def learn_rules_from_turn(user_input, final_answer, confidence=0.0, engagement_hint=""):
    lowered_user = (user_input or "").lower()
    lowered_answer = (final_answer or "").lower()
    created = []

    if len((final_answer or "").split()) <= 45:
        created.append(upsert_rule("brevity_preferred", "Prefer compact answers unless detail is clearly needed.", weight=0.82, source="observed_reply_length"))
    if any(word in lowered_user for word in ("career", "study", "college", "abroad", "biotech", "job")):
        created.append(upsert_rule("career_priority", "Prioritize career and study guidance when relevant.", weight=0.84, source="topic_frequency"))
    if any(word in lowered_user for word in ("gym", "fitness", "diet", "workout")):
        created.append(upsert_rule("fitness_priority", "Prioritize fitness consistency advice when fitness appears in context.", weight=0.78, source="topic_frequency"))
    if "confidence:" in lowered_answer and float(confidence or 0.0) < 0.6:
        created.append(upsert_rule("caution_on_uncertainty", "When certainty is limited, openly state uncertainty and reduce overclaiming.", weight=0.88, source="low_confidence_turn"))
    if engagement_hint:
        created.append(upsert_rule(f"engagement_{engagement_hint}", engagement_hint, weight=0.6, source="engagement_hint"))
    return created

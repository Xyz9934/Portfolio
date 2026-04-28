import json
import os
from datetime import datetime

from assistant_memory import update_conversation_summary


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "friday_learning_log.jsonl")


def log_interaction(user_text, reply_text, source="chat"):
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "source": source,
        "user": user_text,
        "reply": reply_text,
    }

    with open(LOG_FILE, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    try:
        update_conversation_summary()
    except Exception:
        pass

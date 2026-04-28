import os
import time
from assistant_memory import ensure_assistant_storage

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _memory_file_path():
    try:
        from kivy.app import App

        app = App.get_running_app()
        if app and getattr(app, "user_data_dir", None):
            return os.path.join(app.user_data_dir, "friday_memory.json")
    except Exception:
        pass

    return os.path.join(BASE_DIR, "friday_memory.json")


def _touch_json_file(path, default_text="[]"):
    os.makedirs(os.path.dirname(path) or BASE_DIR, exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(default_text)


def _touch_text_file(path):
    os.makedirs(os.path.dirname(path) or BASE_DIR, exist_ok=True)
    if not os.path.exists(path):
        with open(path, "a", encoding="utf-8"):
            pass


def ensure_local_storage_files():
    ensure_assistant_storage()
    knowledge_path = os.path.join(BASE_DIR, "knowledge.json")
    memory_path = _memory_file_path()
    learning_log_path = os.path.join(BASE_DIR, "friday_learning_log.jsonl")

    _touch_json_file(knowledge_path)
    _touch_json_file(memory_path)
    _touch_text_file(learning_log_path)

    return {
        "knowledge": knowledge_path,
        "memory": memory_path,
        "learning_log": learning_log_path,
    }


def is_storage_status_command(text):
    normalized = (text or "").strip().lower()
    phrases = {
        "storage status",
        "memory status",
        "backend status",
        "check storage",
        "check memory backends",
    }
    return normalized in phrases


def get_storage_status():
    started_at = time.perf_counter()
    paths = ensure_local_storage_files()
    knowledge_path = paths["knowledge"]
    memory_path = paths["memory"]
    learning_log_path = paths["learning_log"]
    debug_lines = ["Checking storage backends..."]

    local_status = []
    local_status.append(f"knowledge.json: {'connected' if os.path.exists(knowledge_path) else 'missing'}")
    local_status.append(f"friday_memory.json: {'connected' if os.path.exists(memory_path) else 'missing'}")
    local_status.append(f"learning_log: {'connected' if os.path.exists(learning_log_path) else 'missing'}")

    try:
        debug_lines.append("Trying Pinecone...")
        from semantic_brain import get_pinecone_status

        pinecone_status = get_pinecone_status()
    except Exception:
        pinecone_status = "unreachable"
        debug_lines.append("Pinecone unavailable.")
    else:
        debug_lines.append(f"Pinecone: {pinecone_status}")

    try:
        debug_lines.append("Trying Firebase Realtime Database...")
        from cloud_memory import firebase_ready
        from config import FIREBASE_ENABLED

        firebase_status = "disabled" if not FIREBASE_ENABLED else ("connected" if firebase_ready() else "unreachable")
    except Exception:
        firebase_status = "unreachable"
        debug_lines.append("Firebase unavailable.")
    else:
        debug_lines.append(f"Firebase Realtime Database: {firebase_status}")
    try:
        debug_lines.append("Trying Firestore...")
        from cloud_brain import get_firestore_status

        firestore_status = get_firestore_status()
    except Exception:
        firestore_status = "unreachable"
        debug_lines.append("Firestore unavailable.")
    else:
        debug_lines.append(f"Firestore: {firestore_status}")

    elapsed = time.perf_counter() - started_at

    return (
        "\n".join(debug_lines)
        + f"\nChecked in {elapsed:.2f}s.\n\n"
        + "Storage status:\n"
        + "\n".join(f"- {item}" for item in local_status)
        + f"\n- Pinecone: {pinecone_status}"
        + f"\n- Firebase Realtime Database: {firebase_status}"
        + f"\n- Firestore: {firestore_status}"
    )

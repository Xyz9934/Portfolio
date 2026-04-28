import json
import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RUNTIME_STATE_FILE = os.path.join(BASE_DIR, "brain_runtime_state.json")


def _load_state():
    try:
        with open(RUNTIME_STATE_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"pending_pc_command": ""}


def _save_state(state):
    with open(RUNTIME_STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2)


def set_pending_pc_command(command):
    state = _load_state()
    state["pending_pc_command"] = (command or "").strip()
    _save_state(state)


def get_pending_pc_command():
    return _load_state().get("pending_pc_command", "").strip()


def has_pending_pc_command():
    return bool(get_pending_pc_command())


def clear_pending_pc_command():
    state = _load_state()
    state["pending_pc_command"] = ""
    _save_state(state)

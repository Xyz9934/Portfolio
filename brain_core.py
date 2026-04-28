import json
import os
from kivy.app import App


def get_memory_file():
    app = App.get_running_app()
    if app and getattr(app, "user_data_dir", None):
        os.makedirs(app.user_data_dir, exist_ok=True)
        return os.path.join(app.user_data_dir, "friday_memory.json")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "friday_memory.json")


def ensure_memory_file():
    memory_file = get_memory_file()
    memory_dir = os.path.dirname(memory_file)
    if memory_dir:
        os.makedirs(memory_dir, exist_ok=True)
    if not os.path.exists(memory_file):
        with open(memory_file, "w", encoding="utf-8") as f:
            json.dump([], f)
    return memory_file


class BrainCore:

    def __init__(self):
        self.memory = self.load_memory()

    def load_memory(self):
        memory_file = ensure_memory_file()

        try:
            with open(memory_file, "r", encoding="utf-8") as f:
                return json.load(f)

        except Exception:
            return []

    def save_memory(self):
        memory_file = ensure_memory_file()

        with open(memory_file, "w", encoding="utf-8") as f:
            json.dump(self.memory, f, ensure_ascii=False, indent=2)

    def recall(self):

        return "\n".join(self.memory[-6:])

    def store(self, user, reply):

        self.memory.append(f"User: {user}")
        self.memory.append(f"FRIDAY: {reply}")

        self.save_memory()

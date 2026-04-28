import importlib
import sys


class KernelBootstrap:

    def __init__(self):

        self.core_modules = [
            "brain_core",
            "search_brain",
            "audio_core",
            "scheduler_core"
        ]

    def check_dependencies(self):

        try:
            import kivy
            import requests

            return True

        except Exception as e:

            print("Dependency Error:", e)
            return False


    def load_cores(self):

        loaded = {}

        try:

            for module_name in self.core_modules:

                loaded[module_name] = importlib.import_module(module_name)

                print(f"[KERNEL] Loaded {module_name}")

            return loaded

        except Exception as e:

            print("Kernel Load Error:", e)
            sys.exit()


    def start(self, hud_launcher):

        print("FRIDAY Kernel Boot Sequence Starting...")

        if not self.check_dependencies():
            print("Missing Dependencies")
            return

        cores = self.load_cores()

        print("Memory Brain Initialized")

        hud_launcher()


kernel = KernelBootstrap()

import threading
from mobile_voice_core import speak


def speak_stream(text):

    if not text:
        return

    def worker():

        try:
            for chunk in text.split(". "):
                speak(chunk)

        except Exception as e:
            print("Speech Error:", e)

    threading.Thread(target=worker, daemon=True).start()

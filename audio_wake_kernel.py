import speech_recognition as sr
import threading

WAKE_WORD = "hey friday"


def start_wake_listener(callback):

    def worker():

        recognizer = sr.Recognizer()
        microphone = sr.Microphone()

        while True:

            try:

                with microphone as source:
                    recognizer.adjust_for_ambient_noise(source)

                    audio = recognizer.listen(source, timeout=5)

                text = recognizer.recognize_google(audio).lower()

                if WAKE_WORD in text:
                    callback()

            except:
                pass

    threading.Thread(target=worker, daemon=True).start()

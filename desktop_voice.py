import threading
import json
import os
import time

try:
    import speech_recognition as sr
except Exception:
    sr = None

try:
    from vosk import KaldiRecognizer, Model as VoskModel
except Exception:
    VoskModel = None
    KaldiRecognizer = None

try:
    import pyaudio
except Exception:
    pyaudio = None


def microphone_available():
    return sr is not None or (VoskModel is not None and pyaudio is not None)


def listen_once(on_result, on_error):
    if sr is None and VoskModel is not None and KaldiRecognizer is not None and pyaudio is not None:
        _listen_once_vosk(on_result, on_error)
        return

    if sr is None:
        on_error("Microphone is not available on this PC.")
        return

    def worker():
        recognizer = sr.Recognizer()

        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=8)

            text = recognizer.recognize_google(audio)
            on_result(text)
        except sr.WaitTimeoutError:
            on_error("I didn't hear anything.")
        except sr.UnknownValueError:
            on_error("I couldn't understand the microphone input.")
        except Exception as exc:
            on_error(f"Microphone error: {exc}")

    threading.Thread(target=worker, daemon=True).start()


def _listen_once_vosk(on_result, on_error, timeout_seconds=8):
    model_path = find_vosk_model_path()
    if not model_path:
        on_error("Vosk model not found in local_models.")
        return

    def worker():
        try:
            model = VoskModel(model_path)
            recognizer = KaldiRecognizer(model, 16000)
            audio = pyaudio.PyAudio()
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=4096,
            )
            stream.start_stream()
        except Exception as exc:
            on_error(f"Offline microphone error: {exc}")
            return

        deadline = time.time() + timeout_seconds
        partial_text = ""

        try:
            while time.time() < deadline:
                data = stream.read(4096, exception_on_overflow=False)
                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result() or "{}")
                    text = (result.get("text") or "").strip()
                    if text:
                        on_result(text)
                        return

                partial = json.loads(recognizer.PartialResult() or "{}")
                partial_text = (partial.get("partial") or "").strip() or partial_text

            if partial_text:
                on_result(partial_text)
            else:
                on_error("I didn't hear anything.")
        except Exception as exc:
            on_error(f"Offline microphone error: {exc}")
        finally:
            try:
                stream.stop_stream()
                stream.close()
                audio.terminate()
            except Exception:
                pass

    threading.Thread(target=worker, daemon=True).start()


def start_wake_listener(on_wake, wake_word="friday"):
    if try_start_vosk_wake_listener(on_wake, wake_word=wake_word):
        return

    if sr is None:
        return

    def worker():
        recognizer = sr.Recognizer()

        try:
            microphone = sr.Microphone()
        except Exception:
            return

        while True:
            try:
                with microphone as source:
                    recognizer.adjust_for_ambient_noise(source, duration=0.3)
                    audio = recognizer.listen(source, timeout=3, phrase_time_limit=3)

                text = recognizer.recognize_google(audio).lower().strip()
                if wake_word in text or f"hey {wake_word}" in text:
                    on_wake()
            except Exception:
                pass

    threading.Thread(target=worker, daemon=True).start()


def try_start_vosk_wake_listener(on_wake, wake_word="friday"):
    model_path = find_vosk_model_path()
    if not model_path or VoskModel is None or KaldiRecognizer is None or pyaudio is None:
        return False

    def worker():
        try:
            model = VoskModel(model_path)
            recognizer = KaldiRecognizer(model, 16000)
            audio = pyaudio.PyAudio()
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=4096,
            )
            stream.start_stream()
        except Exception:
            return

        phrases = {wake_word.lower().strip(), f"hey {wake_word.lower().strip()}"}

        try:
            while True:
                data = stream.read(4096, exception_on_overflow=False)
                if not recognizer.AcceptWaveform(data):
                    continue

                result = json.loads(recognizer.Result() or "{}")
                text = (result.get("text") or "").lower().strip()
                if text in phrases or any(phrase in text for phrase in phrases):
                    on_wake()
        except Exception:
            pass
        finally:
            try:
                stream.stop_stream()
                stream.close()
                audio.terminate()
            except Exception:
                pass

    threading.Thread(target=worker, daemon=True).start()
    return True


def find_vosk_model_path():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    local_models_dir = os.path.join(base_dir, "local_models")
    if not os.path.isdir(local_models_dir):
        return None

    for name in os.listdir(local_models_dir):
        candidate = os.path.join(local_models_dir, name)
        if os.path.isdir(candidate) and "vosk" in name.lower():
            resolved = resolve_vosk_model_dir(candidate)
            if resolved:
                return resolved

    return None


def resolve_vosk_model_dir(root_dir):
    if is_vosk_model_dir(root_dir):
        return root_dir

    try:
        for name in os.listdir(root_dir):
            candidate = os.path.join(root_dir, name)
            if os.path.isdir(candidate) and is_vosk_model_dir(candidate):
                return candidate
    except Exception:
        return None

    return None


def is_vosk_model_dir(path):
    required_paths = [
        os.path.join(path, "am"),
        os.path.join(path, "conf"),
        os.path.join(path, "graph"),
    ]
    return all(os.path.exists(item) for item in required_paths)

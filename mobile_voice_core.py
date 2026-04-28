import os
import queue
import subprocess
import threading
from datetime import datetime

from plyer import tts

speech_queue = queue.Queue()
worker_started = False
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tts_debug.log")
CURRENT_VOICE_STYLE = {"rate": 0, "tag": "normal"}


def ensure_worker():
    global worker_started
    if worker_started:
        return

    worker_started = True
    threading.Thread(target=speech_worker, daemon=True).start()


def speech_worker():
    while True:
        text = speech_queue.get()
        try:
            speak_now(text)
        finally:
            speech_queue.task_done()


def speak_now(text):
    if not text or not str(text).strip():
        return

    log_tts_event("start", text)

    try:
        if os.name == "nt":
            log_tts_event("windows_voice", text)
            escaped = str(text).replace("'", "''")
            subprocess.run(
                [
                    "powershell",
                    "-Command",
                    f"Add-Type -AssemblyName System.Speech; "
                    f"$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                    f"$speak.Rate = {int(CURRENT_VOICE_STYLE.get('rate', 0))}; "
                    f"$voice = $speak.GetInstalledVoices() | "
                    f"ForEach-Object {{ $_.VoiceInfo }} | "
                    f"Where-Object {{ $_.Name -like '*Heera*' }} | "
                    f"Select-Object -First 1; "
                    f"if ($voice) {{ $speak.SelectVoice($voice.Name) }}; "
                    f"$speak.Speak('{escaped}')",
                ],
                check=False,
                timeout=120,
            )
            log_tts_event("windows_voice_done", text)
            return
    except Exception as exc:
        log_tts_error("windows_speech", text, exc)

    try:
        log_tts_event("plyer_fallback", text)
        tts.speak(text)
        log_tts_event("plyer_fallback_done", text)
    except Exception as exc:
        log_tts_error("plyer_tts", text, exc)
        print("TTS not available")


def speak(text):
    ensure_worker()
    speech_queue.put(str(text))


def set_voice_style(style=None):
    global CURRENT_VOICE_STYLE
    if isinstance(style, dict):
        CURRENT_VOICE_STYLE = {
            "rate": int(style.get("rate", 0)),
            "tag": str(style.get("tag", "normal")),
        }
    else:
        CURRENT_VOICE_STYLE = {"rate": 0, "tag": "normal"}


def log_tts_error(source, text, exc=None):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            message = f"[{datetime.now().isoformat()}] {source} failed for text: {text[:120]}"
            if exc is not None:
                message += f" | error: {exc}"
            f.write(message + "\n")
    except Exception:
        pass


def log_tts_event(stage, detail):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {stage}: {str(detail)[:160]}\n")
    except Exception:
        pass

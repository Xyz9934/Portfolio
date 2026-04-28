import ctypes
import os
import re
import subprocess
import time
import webbrowser
from pathlib import Path
from urllib.parse import quote

import requests

try:
    import pyautogui
except Exception:
    pyautogui = None


APP_ALIASES = {
    "powershell": ["powershell"],
    "command prompt": ["cmd"],
    "cmd": ["cmd"],
    "notepad": ["notepad"],
    "calculator": ["calc"],
    "paint": ["mspaint"],
    "wordpad": ["write"],
    "explorer": ["explorer"],
    "file explorer": ["explorer"],
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        "chrome",
    ],
    "edge": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        "msedge",
    ],
    "brave": [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        "brave",
    ],
    "vscode": [
        r"C:\Users\DARK_SOUL\AppData\Local\Programs\Microsoft VS Code\Code.exe",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Programs\Microsoft VS Code\Code.exe"),
        "code",
    ],
}

FILE_TYPE_WORDS = {
    "pdf": ".pdf",
    "text": ".txt",
    "txt": ".txt",
    "doc": ".doc",
    "docx": ".docx",
    "png": ".png",
    "jpg": ".jpg",
}

VK_CODES = {
    " ": 0x20,
    ".": 0xBE,
    ",": 0xBC,
    "-": 0xBD,
    "/": 0xBF,
    "\\": 0xDC,
    ";": 0xBA,
    ":": 0xBA,
    "'": 0xDE,
    '"': 0xDE,
    "[": 0xDB,
    "]": 0xDD,
    "=": 0xBB,
    "_": 0xBD,
    "!": 0x31,
    "?": 0xBF,
}

KEYEVENTF_KEYUP = 0x0002
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
PATH_CACHE = {}
YES_WORDS = {"yes", "confirm", "do it", "go ahead", "proceed", "okay", "ok"}
NO_WORDS = {"no", "cancel", "stop", "never mind", "dont", "don't"}
RISKY_ACTIONS = {
    "shutdown": {
        "phrases": ("shutdown pc", "shutdown computer", "shut down pc", "shut down computer", "shutdown my pc"),
        "message": "This will shut down your PC immediately. Reply yes to confirm or no to cancel.",
    },
    "restart": {
        "phrases": ("restart pc", "restart computer", "restart my pc"),
        "message": "This will restart your PC immediately. Reply yes to confirm or no to cancel.",
    },
    "lock": {
        "phrases": ("lock pc", "lock computer", "lock my pc", "lock my computer"),
        "message": "This will lock your PC right away. Reply yes to confirm or no to cancel.",
    },
    "type": {
        "phrases": (),
        "message": "This will type text into the active window. Reply yes to confirm or no to cancel.",
    },
}


def normalize_text(text):
    return re.sub(r"\s+", " ", text.lower()).strip()


def is_windows():
    return os.name == "nt"


def is_confirmation_reply(command):
    normalized = normalize_text(command)
    return normalized in YES_WORDS or normalized in NO_WORDS


def is_positive_confirmation(command):
    return normalize_text(command) in YES_WORDS


def get_risky_action(command):
    text = normalize_text(command)
    if text.startswith("type "):
        return "type"

    for action, data in RISKY_ACTIONS.items():
        if any(phrase in text for phrase in data["phrases"]):
            return action
    return ""


def get_confirmation_message(command):
    action = get_risky_action(command)
    if not action:
        return ""
    return RISKY_ACTIONS[action]["message"]


def execute_pc_command(command, allow_risky=False):
    if not is_windows():
        return "PC control is available only on Windows."

    text = normalize_text(command)
    if not text:
        return None

    risky_action = get_risky_action(command)
    if risky_action and not allow_risky:
        return {"needs_confirmation": True, "message": get_confirmation_message(command), "command": command}

    direct_path = extract_windows_path(command)
    if direct_path:
        return open_path(direct_path)

    if any(phrase in text for phrase in ("lock pc", "lock computer", "lock my pc", "lock my computer")):
        ctypes.windll.user32.LockWorkStation()
        return "Locking your PC."

    if any(phrase in text for phrase in ("shutdown pc", "shutdown computer", "shut down pc", "shut down computer", "shutdown my pc")):
        subprocess.Popen(["shutdown", "/s", "/t", "0"])
        return "Shutting down your PC."

    if any(phrase in text for phrase in ("restart pc", "restart computer", "restart my pc")):
        subprocess.Popen(["shutdown", "/r", "/t", "0"])
        return "Restarting your PC."

    if any(phrase in text for phrase in ("cancel shutdown", "stop shutdown")):
        subprocess.Popen(["shutdown", "/a"])
        return "Shutdown cancelled."

    youtube_reply = handle_youtube_transport_command(text)
    if youtube_reply:
        return youtube_reply

    transport_reply = handle_transport_command(text)
    if transport_reply:
        return transport_reply

    volume_reply = handle_volume_command(text)
    if volume_reply:
        return volume_reply

    if text.startswith("type "):
        content = command.strip()[5:]
        if not content:
            return "Tell me what to type."
        type_text(content)
        return f"Typed: {content}"

    media_reply = handle_media_command(command)
    if media_reply:
        return media_reply

    open_reply = handle_open_command(command)
    if open_reply:
        return open_reply

    search_reply = handle_search_command(command)
    if search_reply:
        return search_reply

    return None


def handle_media_command(command):
    text = normalize_text(command)

    spotify_patterns = [
        r"(?:play|open)\s+(.+?)\s+(?:music\s+)?on\s+spotify",
        r"play\s+(.+?)\s+in\s+spotify",
        r"spotify\s+play\s+(.+)",
    ]
    youtube_patterns = [
        r"(?:play|open)\s+(.+?)\s+(?:music\s+)?on\s+youtube",
        r"play\s+(.+?)\s+in\s+youtube",
        r"youtube\s+play\s+(.+)",
    ]

    for pattern in spotify_patterns:
        match = re.search(pattern, text)
        if match:
            query = cleanup_tokens(match.group(1))
            if not query:
                return "Tell me what to play on Spotify."
            return play_on_spotify(query)

    for pattern in youtube_patterns:
        match = re.search(pattern, text)
        if match:
            query = cleanup_tokens(match.group(1))
            if not query:
                return "Tell me what to play on YouTube."
            return play_on_youtube(query)

    return None


def play_on_spotify(query):
    encoded = quote(query)
    browser_url = f"https://open.spotify.com/search/{encoded}"

    opened_app = False

    try:
        os.startfile(f"spotify:search:{query}")
        opened_app = True
    except Exception:
        opened_app = False

    try:
        webbrowser.open(browser_url)
    except Exception:
        if opened_app:
            return f"Opened Spotify for {query}."
        return "I couldn't open Spotify."

    threading_playback_hint("spotify")

    if opened_app:
        return f"Opened Spotify search for {query} and tried to start playback."

    return f"Opened Spotify in the browser for {query} and tried to start playback."


def play_on_youtube(query):
    url = get_youtube_play_url(query)
    try:
        webbrowser.open(url)
        threading_playback_hint("youtube")
        return f"Opened YouTube for {query} and tried to start playback."
    except Exception:
        return "I couldn't open YouTube."


def get_youtube_play_url(query):
    headers = {"User-Agent": "Mozilla/5.0"}
    search_url = f"https://www.youtube.com/results?search_query={quote(query)}"

    try:
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()
        matches = re.findall(r"\/watch\?v=([A-Za-z0-9_-]{11})", response.text)
        if matches:
            return f"https://www.youtube.com/watch?v={matches[0]}&autoplay=1"
    except Exception:
        pass

    return search_url


def threading_playback_hint(target):
    if pyautogui is None:
        return

    def worker():
        time.sleep(4)

        try:
            if target == "youtube":
                pyautogui.press("k")
                time.sleep(0.5)
                pyautogui.press("f")
            elif target == "spotify":
                pyautogui.press("tab", presses=8, interval=0.15)
                pyautogui.press("enter")
                time.sleep(0.8)
                press_virtual_key(VK_MEDIA_PLAY_PAUSE)
        except Exception:
            pass

    import threading
    threading.Thread(target=worker, daemon=True).start()


def handle_transport_command(text):
    if any(phrase in text for phrase in ("pause spotify", "pause music", "play pause", "resume spotify", "resume music")):
        press_virtual_key(VK_MEDIA_PLAY_PAUSE)
        return "Toggled play and pause."

    if any(phrase in text for phrase in ("next song", "next track", "spotify next", "skip song")):
        press_virtual_key(VK_MEDIA_NEXT_TRACK)
        return "Skipped to the next track."

    if any(phrase in text for phrase in ("previous song", "previous track", "prev song", "spotify previous", "last song")):
        press_virtual_key(VK_MEDIA_PREV_TRACK)
        return "Went back to the previous track."

    return None


def handle_youtube_transport_command(text):
    if any(phrase in text for phrase in ("like this video", "like current video")):
        return control_youtube("like")

    if "youtube" not in text:
        return None

    if any(phrase in text for phrase in ("pause youtube", "resume youtube", "play youtube", "youtube pause", "youtube resume")):
        return control_youtube("toggle")

    if any(phrase in text for phrase in ("next youtube video", "youtube next", "next video on youtube")):
        return control_youtube("next")

    if any(phrase in text for phrase in ("previous youtube video", "youtube previous", "last youtube video", "previous video on youtube")):
        return control_youtube("previous")

    if any(phrase in text for phrase in ("mute youtube", "unmute youtube", "youtube mute")):
        return control_youtube("mute")

    if any(phrase in text for phrase in ("fullscreen youtube", "youtube fullscreen")):
        return control_youtube("fullscreen")

    if any(phrase in text for phrase in ("seek forward youtube", "forward youtube", "youtube forward", "skip forward youtube")):
        return control_youtube("forward")

    if any(phrase in text for phrase in ("seek backward youtube", "backward youtube", "youtube backward", "rewind youtube")):
        return control_youtube("backward")

    if any(phrase in text for phrase in ("increase youtube speed", "youtube faster", "speed up youtube")):
        return control_youtube("speed_up")

    if any(phrase in text for phrase in ("decrease youtube speed", "youtube slower", "slow down youtube")):
        return control_youtube("speed_down")

    if any(phrase in text for phrase in ("captions on youtube", "captions off youtube", "toggle captions youtube", "youtube captions")):
        return control_youtube("captions")

    if any(phrase in text for phrase in ("like youtube video", "youtube like")):
        return control_youtube("like")

    return None


def control_youtube(action):
    if pyautogui is None:
        return "YouTube automation needs pyautogui, and it is not available."

    def worker():
        try:
            time.sleep(0.3)
            pyautogui.hotkey("alt", "tab")
            time.sleep(0.3)

            if action == "toggle":
                pyautogui.press("k")
            elif action == "next":
                pyautogui.hotkey("shift", "n")
            elif action == "previous":
                pyautogui.hotkey("shift", "p")
            elif action == "mute":
                pyautogui.press("m")
            elif action == "fullscreen":
                pyautogui.press("f")
            elif action == "forward":
                pyautogui.press("l")
            elif action == "backward":
                pyautogui.press("j")
            elif action == "speed_up":
                pyautogui.hotkey("shift", ".")
            elif action == "speed_down":
                pyautogui.hotkey("shift", ",")
            elif action == "captions":
                pyautogui.press("c")
            elif action == "like":
                if not try_click_visible_target("click like top right"):
                    pyautogui.press("tab", presses=6, interval=0.12)
                    pyautogui.press("enter")
        except Exception:
            pass

    import threading
    threading.Thread(target=worker, daemon=True).start()

    if action == "toggle":
        return "Sent play/pause to YouTube."

    if action == "next":
        return "Sent next-video command to YouTube."

    if action == "previous":
        return "Sent previous-video command to YouTube."

    if action == "mute":
        return "Toggled mute on YouTube."

    if action == "fullscreen":
        return "Toggled fullscreen on YouTube."

    if action == "forward":
        return "Skipped forward on YouTube."

    if action == "backward":
        return "Skipped backward on YouTube."

    if action == "speed_up":
        return "Increased YouTube playback speed."

    if action == "speed_down":
        return "Decreased YouTube playback speed."

    if action == "captions":
        return "Toggled YouTube captions."

    if action == "like":
        return "Tried to like the current YouTube video."

    return None


def try_click_visible_target(command):
    try:
        from screen_vision import click_from_recent_or_new_snapshot

        result = click_from_recent_or_new_snapshot(command)
        return isinstance(result, str) and result.lower().startswith("clicked ")
    except Exception:
        return False


def handle_volume_command(text):
    if "mute" in text and "volume" in text or text == "mute":
        press_virtual_key(VK_VOLUME_MUTE)
        return "Toggled mute."

    if any(phrase in text for phrase in ("volume up", "increase volume", "sound up")):
        repeat_key(VK_VOLUME_UP, times=5)
        return "Increased volume."

    if any(phrase in text for phrase in ("volume down", "decrease volume", "sound down")):
        repeat_key(VK_VOLUME_DOWN, times=5)
        return "Decreased volume."

    return None


def extract_windows_path(text):
    match = re.search(r"([A-Za-z]:\\[^\n\r\"<>|?*]*)", text)
    if match:
        return match.group(1).strip()
    return None


def handle_open_command(command):
    text = normalize_text(command)
    if not text.startswith("open "):
        return None

    for alias, targets in APP_ALIASES.items():
        if alias in text:
            return open_app(alias, targets)

    drive_match = re.search(r"\b([a-z])\s*drive\b", text)
    if drive_match and ("folder" not in text and "file" not in text and "pdf" not in text):
        return open_path(f"{drive_match.group(1).upper()}:\\")

    path = resolve_path_from_command(command)
    if path:
        return open_path(path)

    return "I couldn't find that app, file, or folder on your PC."


def handle_search_command(command):
    text = normalize_text(command)
    if not (text.startswith("search ") or text.startswith("find ")):
        return None

    path = resolve_path_from_command(command, open_target=False)
    if path:
        return f"I found it here: {path}"

    return "I couldn't find a matching file or folder."


def resolve_path_from_command(command, open_target=True):
    text = normalize_text(command)
    drive = extract_drive(text)
    folder_terms = extract_folder_terms(text)
    file_name = extract_filename(command)
    extension = extract_extension(text)

    if file_name and extension and not file_name.lower().endswith(extension):
        file_name = f"{file_name}{extension}"

    cache_key = (drive or "", tuple(folder_terms), file_name or "", open_target)
    if cache_key in PATH_CACHE:
        return PATH_CACHE[cache_key]

    if file_name and folder_terms:
        folder_path = find_folder(folder_terms, drive=drive)
        if folder_path:
            path = find_file_in_root(folder_path, file_name)
            if path:
                PATH_CACHE[cache_key] = path
                return path

    if file_name:
        path = find_file(file_name=file_name, drive=drive, folder_terms=folder_terms)
        if path:
            PATH_CACHE[cache_key] = path
            return path

    if folder_terms:
        path = find_folder(folder_terms, drive=drive)
        if path:
            PATH_CACHE[cache_key] = path
            return path

    if open_target and drive:
        path = f"{drive}:\\"
        PATH_CACHE[cache_key] = path
        return path

    return None


def extract_drive(text):
    match = re.search(r"\b([a-z])\s*drive\b", text)
    if match:
        return match.group(1).upper()
    return None


def extract_folder_terms(text):
    terms = []

    patterns = [
        r"\bin ([a-z0-9 _-]+?) folder\b",
        r"\bfrom ([a-z0-9 _-]+?) folder\b",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, text):
            term = cleanup_tokens(match.group(1))
            if term and term not in terms:
                terms.append(term)

    return terms


def extract_filename(command):
    original = command.strip()
    lower = normalize_text(command)

    quoted = re.search(r'"([^"]+)"', original)
    if quoted:
        return quoted.group(1).strip()

    patterns = [
        r"open ([a-z0-9 _.-]+?) in [a-z0-9 _.-]+ folder",
        r"open ([a-z0-9 _.-]+?) from [a-z0-9 _.-]+ folder",
        r"open ([a-z0-9 _.-]+?)$",
        r"find ([a-z0-9 _.-]+?)$",
        r"search .* for ([a-z0-9 _.-]+?)$",
    ]

    for pattern in patterns:
        match = re.search(pattern, lower)
        if match:
            return strip_file_type_words(cleanup_tokens(match.group(1)))

    return None


def extract_extension(text):
    for word, extension in FILE_TYPE_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", text):
            return extension
    return ""


def strip_file_type_words(text):
    words = []
    for part in text.split():
        if part not in FILE_TYPE_WORDS:
            words.append(part)
    return " ".join(words).strip()


def cleanup_tokens(text):
    text = re.sub(r"\bthis pc\b", " ", text)
    text = re.sub(r"\bhard drive\b", " ", text)
    text = re.sub(r"\b(file|folder|drive|hard|that|the|in|from|on|my|please|pc)\b", " ", text)
    text = re.sub(r"\b[a-z]\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text


def find_folder(folder_terms, drive=None):
    search_roots = get_search_roots(drive)
    normalized_terms = [term.lower() for term in folder_terms if term]

    for root in search_roots:
        for current_root, dirs, _ in os.walk(root):
            lowered = current_root.lower()
            if all(term in lowered for term in normalized_terms):
                return current_root
            dirs[:] = filter_dirs(dirs)
    return None


def find_file(file_name, drive=None, folder_terms=None):
    search_roots = get_search_roots(drive)
    file_name = file_name.lower()
    folder_terms = [term.lower() for term in (folder_terms or []) if term]

    for root in search_roots:
        for current_root, dirs, files in os.walk(root):
            dirs[:] = filter_dirs(dirs)
            lowered_root = current_root.lower()
            if folder_terms and not all(term in lowered_root for term in folder_terms):
                continue

            for file in files:
                file_lower = file.lower()
                if file_lower == file_name or file_name in file_lower:
                    return os.path.join(current_root, file)
    return None


def find_file_in_root(root, file_name):
    file_name = file_name.lower()

    for current_root, dirs, files in os.walk(root):
        dirs[:] = filter_dirs(dirs)
        for file in files:
            file_lower = file.lower()
            if file_lower == file_name or file_name in file_lower:
                return os.path.join(current_root, file)
    return None


def get_search_roots(drive=None):
    if drive:
        root = f"{drive}:\\"
        return [root] if os.path.exists(root) else []

    quick_roots = [
        os.path.expanduser("~"),
        os.path.join(os.path.expanduser("~"), "Desktop"),
        os.path.join(os.path.expanduser("~"), "Documents"),
        os.path.join(os.path.expanduser("~"), "Downloads"),
        r"D:\FRIDAY",
        r"D:\jarvis",
    ]
    return [root for root in quick_roots if os.path.exists(root)]


def filter_dirs(dirs):
    excluded = {"$recycle.bin", "system volume information", "windows", "program files", "program files (x86)"}
    return [d for d in dirs if d.lower() not in excluded]


def open_app(alias, targets):
    for target in targets:
        try:
            if os.path.exists(target):
                os.startfile(target)
                return f"Opened {alias}."
            subprocess.Popen([target])
            return f"Opened {alias}."
        except Exception:
            continue
    return f"I couldn't open {alias}."


def open_path(path):
    if not path:
        return "I couldn't find that path."

    normalized = str(Path(path))
    if os.path.exists(normalized):
        os.startfile(normalized)
        return f"Opened {normalized}"
    return f"I couldn't find {normalized}"


def type_text(text):
    if pyautogui is not None:
        try:
            pyautogui.write(text, interval=0.02)
            return
        except Exception:
            pass

    for char in text:
        type_character(char)


def repeat_key(vk_code, times=1):
    for _ in range(max(1, times)):
        press_virtual_key(vk_code)


def press_virtual_key(vk_code):
    user32 = ctypes.windll.user32
    user32.keybd_event(vk_code, 0, 0, 0)
    user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)


def type_character(char):
    user32 = ctypes.windll.user32
    vk = VK_CODES.get(char)

    if vk is None:
        if char.isalpha():
            vk = ord(char.upper())
        elif char.isdigit():
            vk = ord(char)
        else:
            return

    use_shift = char.isupper() or char in ':_?"!'

    if use_shift:
        user32.keybd_event(0x10, 0, 0, 0)

    user32.keybd_event(vk, 0, 0, 0)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)

    if use_shift:
        user32.keybd_event(0x10, 0, KEYEVENTF_KEYUP, 0)

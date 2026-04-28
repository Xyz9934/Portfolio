import json
import os
import re
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAPTURE_DIR = os.path.join(BASE_DIR, "captures")
SCREEN_MEMORY_FILE = os.path.join(BASE_DIR, "screen_memory.json")
DEFAULT_TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
MAX_SCREEN_HISTORY = 12


try:
    import dxcam
except Exception:
    dxcam = None

try:
    from PIL import Image
except Exception:
    Image = None

try:
    from PIL import ImageGrab
except Exception:
    ImageGrab = None

try:
    import pytesseract
except Exception:
    pytesseract = None

try:
    import pyautogui
except Exception:
    pyautogui = None


def can_handle_screen_command(text):
    normalized = normalize(text)
    triggers = (
        "read screen",
        "scan screen",
        "what is on my screen",
        "screen text",
        "see screen",
        "capture screen",
        "screen question:",
        "ask screen:",
        "ask current screen:",
        "what changed on screen",
        "where should i click",
        "where do i click",
        "find on screen",
        "click on ",
        "click ",
        "press ",
        "tap ",
        "start screen share",
        "stop screen share",
        "share my screen",
    )
    return any(trigger in normalized for trigger in triggers)


def is_start_screen_share_command(text):
    normalized = normalize(text)
    return any(
        phrase in normalized
        for phrase in ("start screen share", "share my screen", "start sharing screen", "watch my screen")
    )


def is_stop_screen_share_command(text):
    normalized = normalize(text)
    return any(
        phrase in normalized
        for phrase in ("stop screen share", "stop sharing screen", "stop watching screen")
    )


def handle_screen_command(text):
    normalized = normalize(text)

    if is_start_screen_share_command(text):
        return "Screen sharing is handled by the desktop app toggle."

    if is_stop_screen_share_command(text):
        return "Screen sharing is handled by the desktop app toggle."

    if normalized.startswith("ask current screen:"):
        question = text.split(":", 1)[1].strip()
        return answer_from_recent_screen(question)

    if "what changed on screen" in normalized:
        return describe_screen_change()

    if looks_like_click_question(text):
        return click_from_recent_or_new_snapshot(text)

    snapshot = capture_screen_snapshot(save_to_memory=True)
    if snapshot.get("error"):
        return snapshot["error"]

    if normalized.startswith("screen question:") or normalized.startswith("ask screen:"):
        question = text.split(":", 1)[1].strip()
        return answer_question_from_snapshot(question, snapshot)

    if "what is on my screen" in normalized or "see screen" in normalized:
        return summarize_snapshot(snapshot)

    return f"Screen text captured from {snapshot['path']}:\n\n{truncate(snapshot['text'], 1500)}"


def capture_screen_snapshot(save_to_memory=True):
    preflight_error = get_preflight_error()
    if preflight_error:
        return {"error": preflight_error}

    configure_tesseract()
    os.makedirs(CAPTURE_DIR, exist_ok=True)

    try:
        camera = dxcam.create()
        frame = camera.grab()
    except Exception:
        frame = None

    if frame is None:
        image = grab_screen_fallback()
        if image is None:
            return {"error": "I couldn't capture the screen."}
    else:
        image = Image.fromarray(frame)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(CAPTURE_DIR, f"screen_{timestamp}.png")

    try:
        image.save(path)
    except Exception as exc:
        return {"error": f"I couldn't save the screen capture: {exc}"}

    text, ocr_items = extract_text_and_boxes(path)
    snapshot = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "path": path,
        "text": text,
        "summary": build_summary(text),
        "ocr_items": ocr_items,
    }

    if save_to_memory:
        save_snapshot(snapshot)

    return snapshot


def get_preflight_error():
    if dxcam is None:
        return "Screen vision needs the `dxcam` Python package."
    if pytesseract is None or Image is None:
        return "Screen vision needs `pytesseract` and `Pillow` installed."
    if not os.path.exists(DEFAULT_TESSERACT_PATH):
        return "Tesseract OCR is not installed at the expected path."
    return ""


def configure_tesseract():
    if pytesseract is None:
        return
    if os.path.exists(DEFAULT_TESSERACT_PATH):
        pytesseract.pytesseract.tesseract_cmd = DEFAULT_TESSERACT_PATH


def grab_screen_fallback():
    if ImageGrab is None:
        return None
    try:
        return ImageGrab.grab(all_screens=True)
    except Exception:
        return None


def extract_text_and_boxes(image_path):
    try:
        image = Image.open(image_path)
        text = clean_text(pytesseract.image_to_string(image))
        raw = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        width, height = image.size
    except Exception:
        return "", []

    items = []
    line_groups = {}
    total = len(raw.get("text", []))
    for index in range(total):
        word = clean_text(raw["text"][index])
        if not word:
            continue
        try:
            conf = float(raw["conf"][index])
        except Exception:
            conf = -1
        if conf < 35:
            continue
        left = int(raw["left"][index])
        top = int(raw["top"][index])
        item_width = int(raw["width"][index])
        item_height = int(raw["height"][index])
        region = classify_region(left + item_width / 2, top + item_height / 2, width, height)
        items.append(
            {
                "text": word,
                "left": left,
                "top": top,
                "width": item_width,
                "height": item_height,
                "region": region,
                "kind": "word",
            }
        )

        line_key = (
            raw.get("block_num", [0])[index],
            raw.get("par_num", [0])[index],
            raw.get("line_num", [0])[index],
        )
        group = line_groups.setdefault(
            line_key,
            {"parts": [], "left": left, "top": top, "right": left + item_width, "bottom": top + item_height},
        )
        group["parts"].append((left, word))
        group["left"] = min(group["left"], left)
        group["top"] = min(group["top"], top)
        group["right"] = max(group["right"], left + item_width)
        group["bottom"] = max(group["bottom"], top + item_height)

    for group in line_groups.values():
        if len(group["parts"]) < 2:
            continue
        ordered_parts = [part for _, part in sorted(group["parts"], key=lambda item: item[0])]
        line_text = clean_text(" ".join(ordered_parts))
        if not line_text:
            continue
        left = group["left"]
        top = group["top"]
        item_width = group["right"] - group["left"]
        item_height = group["bottom"] - group["top"]
        items.append(
            {
                "text": line_text,
                "left": left,
                "top": top,
                "width": item_width,
                "height": item_height,
                "region": classify_region(left + item_width / 2, top + item_height / 2, width, height),
                "kind": "line",
            }
        )

    return text, items


def classify_region(x, y, width, height):
    horizontal = "left" if x < width / 3 else "right" if x > (width * 2 / 3) else "center"
    vertical = "top" if y < height / 3 else "bottom" if y > (height * 2 / 3) else "middle"

    if vertical == "middle" and horizontal == "center":
        return "center"
    if vertical == "middle":
        return horizontal
    if horizontal == "center":
        return vertical
    return f"{vertical} {horizontal}"


def clean_text(text):
    text = re.sub(r"\r", "\n", text or "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build_summary(screen_text):
    lines = [line.strip() for line in screen_text.splitlines() if line.strip()]
    if not lines:
        return "No readable text detected."
    return "\n".join(lines[:10])


def summarize_snapshot(snapshot):
    if not snapshot.get("summary"):
        return f"I captured the screen at {snapshot['path']}, but OCR found no readable text."
    return f"I captured the screen at {snapshot['path']}. Top readable text:\n\n{snapshot['summary']}"


def answer_question_from_snapshot(question, snapshot):
    if not snapshot.get("text"):
        return f"I captured the screen at {snapshot['path']}, but OCR found no readable text."

    if looks_like_click_question(question):
        return guide_click_from_snapshot(question, snapshot)

    lines = [line.strip() for line in snapshot["text"].splitlines() if line.strip()]
    q_tokens = keyword_tokens(question)
    if not q_tokens:
        return summarize_snapshot(snapshot)

    scored = []
    for line in lines:
        line_lower = line.lower()
        overlap = sum(1 for token in q_tokens if token in line_lower)
        if overlap:
            scored.append((overlap, line))

    if scored:
        scored.sort(key=lambda item: item[0], reverse=True)
        best_lines = [line for _, line in scored[:5]]
        return f"Based on the captured screen at {snapshot['path']}, the most relevant text is:\n\n" + "\n".join(best_lines)

    return (
        f"I captured the screen at {snapshot['path']}, but I couldn't find text matching your question. "
        f"Here is the top OCR text:\n\n{truncate(snapshot['text'], 1200)}"
    )


def guide_click_from_snapshot(question, snapshot):
    match = find_click_target(question, snapshot)
    if not match:
        return (
            f"I couldn't find a matching button or label on the latest screen capture. "
            f"Top readable text:\n\n{snapshot.get('summary', 'No readable text detected.')}"
        )

    return f"The best match I found is `{match['text']}` in the {match['region']} area of the screen."


def click_from_recent_or_new_snapshot(command):
    fresh_snapshot = capture_screen_snapshot(save_to_memory=True)
    if fresh_snapshot.get("error"):
        snapshot = latest_screen_snapshot()
        if not snapshot:
            return fresh_snapshot["error"]
    else:
        snapshot = fresh_snapshot

    match = find_click_target(command, snapshot)
    if not match:
        return (
            "I couldn't find a matching target on the latest screen capture. "
            "Try a more exact label, like `click on new chat`."
        )

    if pyautogui is None:
        return f"I found `{match['text']}` in the {match['region']} area, but `pyautogui` is not available for clicking."

    try:
        x = int(match["left"] + match["width"] / 2)
        y = int(match["top"] + match["height"] / 2)
        pyautogui.moveTo(x, y, duration=0.15)
        pyautogui.click(x, y)
        return f"Clicked `{match['text']}` in the {match['region']} area."
    except Exception as exc:
        return f"I found `{match['text']}`, but the click failed: {exc}"


def find_click_target(command, snapshot):
    tokens = keyword_tokens(command)
    if not tokens:
        return None

    ranked = []
    preferred_regions = region_hints(command)
    normalized_command = normalize(command)
    phrase = extract_click_phrase(command)
    phrase_tokens = keyword_tokens(phrase)

    for item in snapshot.get("ocr_items", []):
        label = item["text"]
        item_lower = label.lower()
        overlap = sum(1 for token in tokens if token in item_lower)
        if overlap == 0:
            continue

        exact_phrase = 1 if phrase and normalize(label) == phrase else 0
        starts_with_phrase = 1 if phrase and normalize(label).startswith(phrase) else 0
        all_phrase_tokens = 1 if phrase_tokens and all(token in item_lower for token in phrase_tokens) else 0
        token_ratio = overlap / max(1, len(tokens))
        region_bonus = 1 if item.get("region") in preferred_regions else 0
        command_bonus = 1 if normalize(label) in normalized_command else 0

        kind_bonus = 1 if item.get("kind") == "line" else 0
        ranked.append(
            (
                exact_phrase,
                starts_with_phrase,
                all_phrase_tokens,
                kind_bonus,
                token_ratio,
                region_bonus,
                command_bonus,
                len(label),
                item,
            )
        )

    if not ranked:
        return None

    ranked.sort(key=lambda row: row[:-1], reverse=True)
    return ranked[0][-1]


def extract_click_phrase(text):
    normalized = normalize(text)
    patterns = (
        r"(?:click on|click|press|tap|find on screen)\s+(.+)$",
        r"(?:where should i click|where do i click)\s+(.+)$",
    )

    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            phrase = match.group(1).strip(" .")
            phrase = re.sub(r"\b(button|tab|link|menu|option)\b", "", phrase)
            phrase = re.sub(r"\s+", " ", phrase).strip()
            if phrase:
                return phrase
    return ""


def answer_from_recent_screen(question):
    history = load_screen_history()
    if not history:
        return "I don't have recent screen memory yet. Start screen sharing or run `read screen` first."

    latest = history[-1]
    snapshot = {
        "timestamp": latest.get("timestamp", ""),
        "path": latest.get("path", ""),
        "text": latest.get("text", ""),
        "summary": latest.get("summary", ""),
        "ocr_items": latest.get("ocr_items", []),
    }
    return answer_question_from_snapshot(question, snapshot)


def describe_screen_change():
    history = load_screen_history()
    if len(history) < 2:
        return "I need at least two recent screen captures before I can tell what changed."

    previous = history[-2]
    current = history[-1]
    previous_lines = set(line.strip() for line in previous.get("summary", "").splitlines() if line.strip())
    current_lines = [line.strip() for line in current.get("summary", "").splitlines() if line.strip()]

    new_lines = [line for line in current_lines if line not in previous_lines][:6]
    if not new_lines:
        return "The last two screen captures look very similar. I don't see major readable-text changes."

    return "What changed on screen:\n\n" + "\n".join(new_lines)


def save_snapshot(snapshot):
    history = load_screen_history()
    slim = {
        "timestamp": snapshot.get("timestamp", ""),
        "path": snapshot.get("path", ""),
        "text": snapshot.get("text", ""),
        "summary": snapshot.get("summary", ""),
        "ocr_items": snapshot.get("ocr_items", []),
    }
    history.append(slim)
    history = history[-MAX_SCREEN_HISTORY:]
    with open(SCREEN_MEMORY_FILE, "w", encoding="utf-8") as handle:
        json.dump(history, handle, ensure_ascii=False, indent=2)


def load_screen_history():
    try:
        with open(SCREEN_MEMORY_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def latest_screen_snapshot():
    history = load_screen_history()
    return history[-1] if history else None


def keyword_tokens(text):
    raw = re.findall(r"[a-z0-9]+", (text or "").lower())
    stop = {
        "what", "is", "the", "on", "my", "screen", "from", "this", "that",
        "a", "an", "of", "to", "for", "in", "and", "read", "show", "tell",
        "where", "should", "do", "click", "current",
    }
    return [token for token in raw if token not in stop]


def looks_like_click_question(text):
    normalized = normalize(text)
    return any(
        phrase in normalized
        for phrase in (
            "where should i click",
            "where do i click",
            "find on screen",
            "click on ",
            "click ",
            "press ",
            "tap ",
        )
    )


def region_hints(text):
    normalized = normalize(text)
    hints = set()
    if "left" in normalized:
        hints.update({"left", "top left", "bottom left"})
    if "right" in normalized:
        hints.update({"right", "top right", "bottom right"})
    if "top" in normalized or "upside" in normalized or "upper" in normalized:
        hints.update({"top", "top left", "top right"})
    if "bottom" in normalized or "lower" in normalized:
        hints.update({"bottom", "bottom left", "bottom right"})
    if "center" in normalized or "middle" in normalized:
        hints.add("center")
    return hints


def normalize(text):
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def truncate(text, limit):
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."

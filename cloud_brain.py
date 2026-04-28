from config import FIREBASE_CREDENTIALS_PATH, FIRESTORE_ENABLED, FIRESTORE_PROJECT_ID
from memory_guard import is_relevant_match, score_match

PROJECT_ID = FIRESTORE_PROJECT_ID
BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/knowledge"

firestore_session = None
firestore_error = None

try:
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2 import service_account

    if FIRESTORE_ENABLED and PROJECT_ID and FIREBASE_CREDENTIALS_PATH:
        creds = service_account.Credentials.from_service_account_file(
            FIREBASE_CREDENTIALS_PATH,
            scopes=["https://www.googleapis.com/auth/datastore"],
        )
        firestore_session = AuthorizedSession(creds)
except Exception as exc:
    firestore_error = exc


def learn_cloud(text):
    if not firestore_ready():
        return "Firestore disabled."

    data = {"fields": {"text": {"stringValue": text}}}

    try:
        response = firestore_session.post(BASE_URL, json=data, timeout=10)
        response.raise_for_status()
        return "Stored in Firestore."
    except Exception as exc:
        global firestore_error
        firestore_error = exc
        return "Firestore not reachable."


def ask_cloud(question):
    matches = search_cloud(question, top_k=1)
    return matches[0] if matches else None


def fetch_cloud_documents():
    if not firestore_ready():
        return []

    try:
        response = firestore_session.get(BASE_URL, timeout=10)
        response.raise_for_status()
        docs = response.json().get("documents", [])
    except Exception as exc:
        global firestore_error
        firestore_error = exc
        return []

    texts = []

    for doc in docs:
        fields = doc.get("fields", {})
        text = fields.get("text", {}).get("stringValue")
        if text:
            texts.append(text)

    return texts


def firestore_ready():
    if not FIRESTORE_ENABLED or not PROJECT_ID or firestore_session is None:
        return False

    try:
        response = firestore_session.get(BASE_URL, timeout=10)
        if response.status_code in (200, 404):
            return True
        if response.status_code == 403 and "firestore.googleapis.com" in response.text.lower():
            return False
        response.raise_for_status()
        return True
    except Exception as exc:
        global firestore_error
        firestore_error = exc
        return False


def get_firestore_status():
    if not FIRESTORE_ENABLED:
        return "disabled"
    if not PROJECT_ID or firestore_session is None:
        return "not configured"

    try:
        response = firestore_session.get(BASE_URL, timeout=10)
        if response.status_code in (200, 404):
            return "connected"
        if response.status_code == 403 and "firestore.googleapis.com" in response.text.lower():
            return "api disabled"
        return "unreachable"
    except Exception as exc:
        global firestore_error
        firestore_error = exc
        return "unreachable"


def search_cloud(question, top_k=3):
    scored = []

    for text in fetch_cloud_documents():
        if not is_relevant_match(question, text, strict=True):
            continue

        score, overlap, _ = score_match(question, text)
        scored.append((score, overlap, text))

    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [text for _, _, text in scored[:top_k]]

import os
import firebase_admin
from firebase_admin import credentials, db
from config import FIREBASE_CREDENTIALS_PATH, FIREBASE_DATABASE_URL, FIREBASE_ENABLED
from memory_guard import is_relevant_match, score_match


# ---------- Firebase Setup ----------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

KEY_PATH = FIREBASE_CREDENTIALS_PATH or os.path.join(BASE_DIR, "firebase_key.json")


firebase_error = None


def ensure_firebase_app():
    global firebase_error

    if not FIREBASE_ENABLED:
        firebase_error = None
        return False

    if firebase_admin._apps:
        return True

    try:
        cred = credentials.Certificate(KEY_PATH)
        firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DATABASE_URL})
        firebase_error = None
        return True
    except Exception as exc:
        firebase_error = exc
        return False


ensure_firebase_app()


def firebase_ready():
    return ensure_firebase_app()


# ---------- PDF CHUNK STORAGE ----------

def store_chunk(pdf_name, chunk_id, text, embedding):
    if not firebase_ready():
        return

    ref = db.reference(f"/pdf_knowledge/{pdf_name}/chunk_{chunk_id}")

    ref.set({
        "text": text,
        "embedding": embedding
    })


def get_all_chunks():
    if not firebase_ready():
        return None

    ref = db.reference("/pdf_knowledge")

    return ref.get()


# ---------- FETCH ONLY TEXT CHUNKS ----------

def fetch_all_pdf_chunks():
    if not firebase_ready():
        return []

    ref = db.reference("/pdf_knowledge")

    data = ref.get()

    if not data:
        return []

    chunks = []

    for pdf in data:

        for chunk in data[pdf]:

            chunks.append(data[pdf][chunk]["text"])

    return chunks


# ---------- CLOUD KNOWLEDGE STORAGE ----------

def cloud_store(text):
    if not firebase_ready():
        return "Firebase disabled."

    ref = db.reference("knowledge")

    data = ref.get()

    if not data:
        ref.set([text])
        return "Stored in Firebase Realtime Database."

    if text not in data:
        data.append(text)
        ref.set(data)
        return "Stored in Firebase Realtime Database."

    return "Already stored in Firebase Realtime Database."


# ---------- CLOUD KNOWLEDGE FETCH ----------

def cloud_fetch():
    if not firebase_ready():
        return []

    ref = db.reference("knowledge")

    data = ref.get()

    if not data:
        return []

    return data


def cloud_search(query_text, top_k=3):
    if not FIREBASE_ENABLED:
        return []

    scored = []

    for item in cloud_fetch():
        if not is_relevant_match(query_text, item, strict=True):
            continue

        score, overlap, _ = score_match(query_text, item)
        scored.append((score, overlap, item))

    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [item for _, _, item in scored[:top_k]]

from config import PINECONE_API_KEY, PINECONE_INDEX_NAME
import uuid
import wikipedia
from cloud_brain import learn_cloud
from cloud_memory import cloud_store
from local_knowledge import add_knowledge

index = None
pinecone_error = None


def get_index():
    global index, pinecone_error

    if index is not None or pinecone_error is not None:
        return index

    try:
        from pinecone import Pinecone

        if not PINECONE_API_KEY or not PINECONE_INDEX_NAME:
            raise ValueError("Pinecone is not configured.")

        pc = Pinecone(api_key=PINECONE_API_KEY)
        index = pc.Index(PINECONE_INDEX_NAME)
    except Exception as exc:
        pinecone_error = exc
        index = None

    return index


def pinecone_ready():
    current_index = get_index()
    if current_index is None:
        return False

    try:
        current_index.describe_index_stats()
        return True
    except Exception as exc:
        global pinecone_error, index
        pinecone_error = exc
        index = None
        return False


def get_pinecone_status():
    if not PINECONE_API_KEY or not PINECONE_INDEX_NAME:
        return "not configured"

    if pinecone_ready():
        return "connected"

    if pinecone_error is not None and type(pinecone_error).__name__ == "NotFoundException":
        return "index missing"

    return "unreachable"


def learn_text(text):
    add_knowledge(text)
    stored_backends = ["local memory"]

    try:
        firebase_result = cloud_store(text)
        if firebase_result and "stored" in firebase_result.lower():
            stored_backends.append("Firebase Realtime Database")
    except Exception:
        pass

    try:
        firestore_result = learn_cloud(text)
        if firestore_result and "stored" in firestore_result.lower():
            stored_backends.append("Firestore")
    except Exception:
        pass

    current_index = get_index()
    if current_index is None:
        return "Learned successfully in " + " and ".join(stored_backends) + "."

    from embeddings_local import embed_text

    vector = embed_text(text)

    current_index.upsert([
        {
            "id": str(uuid.uuid4()),
            "values": vector,
            "metadata": {"text": text}
        }
    ])
    stored_backends.append("Pinecone")
    return "Learned successfully in " + " and ".join(stored_backends) + "."


def wiki_search(query):

    try:
        result = wikipedia.summary(query, sentences=3)
        return result
    except:
        return None


def ingest_pdf(path):

    from pdfminer.high_level import extract_text

    print("Reading PDF:", path)

    text = extract_text(path)

    text = clean_pdf_text(text)

    chunks = split_text(text)

    print("Total chunks:", len(chunks))

    for chunk in chunks:
        learn_text(chunk)

    return "PDF learned."


def split_text(text, chunk_size=600, chunk_overlap=120):
    words = text.split()
    chunks = []
    step = max(1, chunk_size - chunk_overlap)

    for i in range(0, len(words), step):
        chunk = " ".join(words[i:i + chunk_size]).strip()
        if chunk:
            chunks.append(chunk)

    return chunks

def clean_pdf_text(text):

    import re

    # join broken lines
    text = re.sub(r'\n+', ' ', text)

    # remove extra spaces
    text = re.sub(r'\s+', ' ', text)

    return text

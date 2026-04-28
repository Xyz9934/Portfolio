import os
from config import EMBED_MODEL

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_MODEL_PATH = os.path.join(BASE_DIR, "local_models", EMBED_MODEL)
model = None
sentence_transformers_available = True

try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None
    sentence_transformers_available = False


def get_model():
    global model

    if model is not None:
        return model

    if not sentence_transformers_available:
        raise RuntimeError("sentence-transformers is not available in this environment")

    if os.path.isdir(LOCAL_MODEL_PATH):
        model = SentenceTransformer(LOCAL_MODEL_PATH, local_files_only=True)
    else:
        model = SentenceTransformer(EMBED_MODEL)

    return model

def embed_text(text):
    vector = get_model().encode(text)
    return vector.tolist()

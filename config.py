import os
import json
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")

if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH, override=True)


def _existing_path(*candidates):
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return candidates[0] if candidates else ""


def _load_service_account():
    candidates = [
        os.getenv("FIREBASE_CREDENTIALS_PATH", ""),
        os.path.join(BASE_DIR, "firebase_key.json"),
        os.path.join(BASE_DIR, "firebase_key.json.json"),
    ]
    path = _existing_path(*candidates)
    if not path or not os.path.exists(path):
        return path, {}

    try:
        with open(path, "r", encoding="utf-8") as handle:
            return path, json.load(handle)
    except Exception:
        return path, {}


def _env_flag(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "friday-ai")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_KEY_BACKUP = os.getenv("GEMINI_API_KEY_BACKUP", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
OPENAI_TTS_MODEL = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
OPENAI_TTS_VOICE = os.getenv("OPENAI_TTS_VOICE", "coral")
OPENAI_TTS_INSTRUCTIONS = os.getenv(
    "OPENAI_TTS_INSTRUCTIONS",
    "Speak in a warm, natural female voice with clear pronunciation.",
)

EMBED_MODEL = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")

OLLAMA_ENABLED = _env_flag("OLLAMA_ENABLED", default=False)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
OLLAMA_QUICK_MODEL = os.getenv("OLLAMA_QUICK_MODEL", OLLAMA_MODEL or "llama3.2")
OLLAMA_DEEP_MODEL = os.getenv("OLLAMA_DEEP_MODEL", "llama3")
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "10m")
PREFER_OFFLINE_BRAIN = _env_flag("PREFER_OFFLINE_BRAIN", default=False)

FIREBASE_CREDENTIALS_PATH, FIREBASE_SERVICE_ACCOUNT = _load_service_account()
FIRESTORE_PROJECT_ID = os.getenv("FIRESTORE_PROJECT_ID", "") or FIREBASE_SERVICE_ACCOUNT.get("project_id", "")
FIREBASE_DATABASE_URL = os.getenv("FIREBASE_DATABASE_URL", "")
FIREBASE_ENABLED = _env_flag("FIREBASE_ENABLED", default=False)
FIRESTORE_ENABLED = _env_flag("FIRESTORE_ENABLED", default=False)

CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
CLOUDFLARE_DATABASE_ID = os.getenv("CLOUDFLARE_DATABASE_ID", "")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "")

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")

DEPLOY_TARGET = os.getenv("DEPLOY_TARGET", "local").strip().lower() or "local"
RENDER_SERVICE = _env_flag("RENDER_SERVICE", default=DEPLOY_TARGET == "render")
CLOUD_SAFE_MODE = _env_flag("CLOUD_SAFE_MODE", default=RENDER_SERVICE)
API_ENABLE_PDF_INGEST = _env_flag("API_ENABLE_PDF_INGEST", default=not CLOUD_SAFE_MODE)
API_ENABLE_LIVE_SEARCH = _env_flag("API_ENABLE_LIVE_SEARCH", default=True)


def remote_knowledge_available():
    return bool(
        (PINECONE_API_KEY and PINECONE_INDEX_NAME)
        or FIREBASE_ENABLED
        or FIRESTORE_ENABLED
    )

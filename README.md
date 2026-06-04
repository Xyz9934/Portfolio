<<<<<<< HEAD
# FRIDAY

FRIDAY is a personal AI assistant project with:

- a local desktop/mobile-oriented runtime
- a Flutter client in [friday_flutter_ui](D:/FRIDAY/friday_flutter_ui)
- a Render-ready Flask API in [server.py](D:/FRIDAY/server.py:1)

## Deployment Safety

Before pushing this repo to GitHub or connecting it to Render:

1. Rotate any previously used API keys.
2. Keep real secrets only in local `.env` files or in Render environment variables.
3. Never commit Firebase service-account JSON files.

This repo now includes:

- [.env.example](D:/FRIDAY/.env.example:1) as the template for local configuration
- [.gitignore](D:/FRIDAY/.gitignore:1) to block secrets and build artifacts

## Local API Run

1. Copy `.env.example` to `.env`.
2. Fill in the keys you actually want to use.
3. Start the API:

```powershell
python D:\FRIDAY\server.py
```

4. Check health:

```powershell
curl http://127.0.0.1:5000/health
```

## Render Deploy

The Render service definition is in [render.yaml](D:/FRIDAY/render.yaml:1).

### GitHub Prep

1. Create a new empty GitHub repo.
2. From `D:\FRIDAY`, run:

```powershell
& 'C:\Program Files\Git\cmd\git.exe' init
& 'C:\Program Files\Git\cmd\git.exe' add .
& 'C:\Program Files\Git\cmd\git.exe' commit -m "Prepare FRIDAY for Render deployment"
& 'C:\Program Files\Git\cmd\git.exe' branch -M main
& 'C:\Program Files\Git\cmd\git.exe' remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
& 'C:\Program Files\Git\cmd\git.exe' push -u origin main
```

3. Make sure `.env`, Firebase key files, local Flutter build output, and runtime memory files are not tracked before pushing.

### Render Setup

1. In Render, choose `New +`.
2. Select `Blueprint` if you want Render to use `render.yaml`, or `Web Service` if you prefer manual setup.
3. Connect your GitHub repo.
4. Confirm these settings:

- Root directory: `.`
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn server:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120`
- Health check path: `/health`

### Required Render Environment Variables

At minimum, set one cloud LLM provider:

- `OPENAI_API_KEY`
or
- `GEMINI_API_KEY`

Recommended core variables:

- `DEPLOY_TARGET=render`
- `RENDER_SERVICE=true`
- `CLOUD_SAFE_MODE=true`
- `API_ENABLE_LIVE_SEARCH=true`
- `API_ENABLE_PDF_INGEST=false`
- `PREFER_OFFLINE_BRAIN=false`
- `OLLAMA_ENABLED=false`
- `GEMINI_MODEL=gemini-2.5-flash`

### Optional Render Environment Variables

Only set these if you use the related service:

- `OPENAI_CHAT_MODEL`
- `PINECONE_API_KEY`
- `PINECONE_INDEX_NAME`
- `FIREBASE_ENABLED`
- `FIREBASE_DATABASE_URL`
- `FIREBASE_CREDENTIALS_PATH`
- `FIRESTORE_ENABLED`
- `FIRESTORE_PROJECT_ID`
- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_DATABASE_ID`
- `CLOUDFLARE_API_TOKEN`

## Safe PDF Ingest on Render

PDF ingest is disabled by default in cloud mode.

That is intentional because Render’s ephemeral filesystem is not a safe long-term storage layer for learned PDF knowledge by itself.

### To enable PDF ingest safely

1. Configure a persistent remote knowledge backend:
- Pinecone, or
- Firebase Realtime Database, or
- Firestore

2. Set the matching environment variables in Render.
3. Turn on:
- `API_ENABLE_PDF_INGEST=true`

### Recommended path

For Render, the cleanest PDF ingest setup is:

- `PINECONE_API_KEY`
- `PINECONE_INDEX_NAME`
- optionally Firebase or Firestore for backup knowledge storage

Without one of those remote backends, PDF ingest is blocked in cloud mode by [render_runtime.py](D:/FRIDAY/render_runtime.py:1).

## First Deploy Checklist

1. Rotate old keys.
2. Push the repo to GitHub.
3. Connect the repo to Render.
4. Add Render environment variables.
5. Deploy.
6. Open `/health`.
7. Test `/ask` with a simple prompt.

## API Endpoints

- `GET /health`
- `POST /ask`
- `POST /upload_pdf`

## Flutter Client

The Flutter app lives in [friday_flutter_ui](D:/FRIDAY/friday_flutter_ui).

To point it at Render later, run with:

```powershell
flutter run --dart-define=FRIDAY_API_BASE_URL=https://your-render-service.onrender.com
```
=======
# FRIDAY
>>>>>>> 48b7c3b5ecb72ef340ac286943854c3fadecc7fc

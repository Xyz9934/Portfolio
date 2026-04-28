import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request

from config import API_ENABLE_PDF_INGEST, DEPLOY_TARGET
from render_runtime import answer_with_render_runtime, ingest_pdf_for_api

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)


def create_app():
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024
    app.config["JSON_SORT_KEYS"] = False

    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return response

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify(
            {
                "status": "ok",
                "service": "friday-backend",
                "deploy_target": DEPLOY_TARGET,
                "pdf_ingest_enabled": API_ENABLE_PDF_INGEST,
            }
        )

    @app.route("/ask", methods=["POST", "OPTIONS"])
    def ask():
        if request.method == "OPTIONS":
            return ("", 204)

        data = request.get_json(silent=True) or {}
        question = str(data.get("question", "")).strip()
        answer_mode = str(data.get("answer_mode", "auto")).strip() or "auto"

        if not question:
            return jsonify({"error": "Question is required"}), 400

        try:
            answer = answer_with_render_runtime(question, answer_mode=answer_mode)
            return jsonify({"answer": answer})
        except Exception as exc:
            return jsonify({"error": "FRIDAY could not process the request", "details": str(exc)}), 500

    @app.route("/upload_pdf", methods=["POST", "OPTIONS"])
    def upload_pdf():
        if request.method == "OPTIONS":
            return ("", 204)

        if not API_ENABLE_PDF_INGEST:
            return jsonify({"error": "PDF ingest is disabled for this deployment"}), 403

        file = request.files.get("file")
        if not file or not file.filename:
            return jsonify({"error": "No file"}), 400

        path = UPLOAD_FOLDER / file.filename
        file.save(path)

        try:
            result = ingest_pdf_for_api(str(path))
        except Exception as exc:
            return jsonify({"error": "PDF ingest failed", "details": str(exc)}), 500

        return jsonify({"status": result, "file": file.filename})

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)

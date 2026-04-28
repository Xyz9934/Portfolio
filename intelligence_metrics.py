import os
import sqlite3
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
METRICS_DB = os.path.join(BASE_DIR, "brain", "intelligence_metrics.db")


def _now():
    return datetime.now().isoformat(timespec="seconds")


def ensure_metrics_storage():
    os.makedirs(os.path.dirname(METRICS_DB), exist_ok=True)
    with sqlite3.connect(METRICS_DB) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS response_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                user_input TEXT NOT NULL,
                response_type TEXT NOT NULL,
                confidence REAL NOT NULL,
                estimated_accuracy REAL NOT NULL,
                usefulness REAL NOT NULL,
                engagement REAL NOT NULL
            )
            """
        )
        conn.commit()


def log_response_metric(user_input, response_type, confidence, estimated_accuracy, usefulness, engagement):
    ensure_metrics_storage()
    with sqlite3.connect(METRICS_DB) as conn:
        conn.execute(
            """
            INSERT INTO response_metrics (
                created_at, user_input, response_type, confidence, estimated_accuracy, usefulness, engagement
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _now(),
                (user_input or "").strip(),
                (response_type or "answer").strip(),
                float(confidence or 0.0),
                float(estimated_accuracy or 0.0),
                float(usefulness or 0.0),
                float(engagement or 0.0),
            ),
        )
        conn.commit()


def estimate_metric_bundle(user_input, final_answer, confidence, response_type="answer"):
    lowered = (user_input or "").lower()
    answer_len = len((final_answer or "").split())
    usefulness = 0.55
    engagement = 0.52

    if any(word in lowered for word in ("how", "plan", "roadmap", "next", "help")):
        usefulness += 0.12
    if "next likely step:" in (final_answer or "").lower():
        usefulness += 0.1
        engagement += 0.08
    if response_type in {"clarify", "challenge"}:
        engagement += 0.06
    if answer_len > 120:
        engagement -= 0.06

    estimated_accuracy = min(0.98, max(0.2, float(confidence or 0.0) + 0.08))
    return {
        "estimated_accuracy": estimated_accuracy,
        "usefulness": min(0.98, max(0.2, usefulness)),
        "engagement": min(0.98, max(0.2, engagement)),
    }


def get_recent_metric_summary(limit=12):
    ensure_metrics_storage()
    with sqlite3.connect(METRICS_DB) as conn:
        rows = conn.execute(
            """
            SELECT response_type, confidence, estimated_accuracy, usefulness, engagement
            FROM response_metrics
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit or 12),),
        ).fetchall()

    if not rows:
        return {
            "count": 0,
            "average_confidence": 0.0,
            "average_accuracy": 0.0,
            "average_usefulness": 0.0,
            "average_engagement": 0.0,
            "clarify_rate": 0.0,
        }

    count = len(rows)
    clarify_count = sum(1 for row in rows if (row[0] or "").strip() == "clarify")
    return {
        "count": count,
        "average_confidence": sum(float(row[1] or 0.0) for row in rows) / count,
        "average_accuracy": sum(float(row[2] or 0.0) for row in rows) / count,
        "average_usefulness": sum(float(row[3] or 0.0) for row in rows) / count,
        "average_engagement": sum(float(row[4] or 0.0) for row in rows) / count,
        "clarify_rate": clarify_count / count,
    }

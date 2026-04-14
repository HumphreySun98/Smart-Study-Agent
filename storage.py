# storage.py
# Persistent student storage using SQLite
# Upgraded from JSON to handle >1k students efficiently
# Haofei Sun - CSE 5360

import json
import sqlite3
import os
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "smartstudy.db"

# keep JSON path for backward compat / migration
_JSON_PATH = DATA_DIR / "students.json"


def _get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_db():
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            name TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            topics_mastered TEXT DEFAULT '[]',
            weak_areas TEXT DEFAULT '[]',
            quiz_history TEXT DEFAULT '[]'
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
            topic TEXT,
            score REAL,
            action TEXT,
            n_questions INTEGER,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (student_name) REFERENCES students(name)
        );
        CREATE INDEX IF NOT EXISTS idx_sessions_student
            ON sessions(student_name);
    """)
    conn.close()


_init_db()


def _migrate_from_json():
    """One-time migration: if old students.json exists, import it."""
    if not _JSON_PATH.exists():
        return
    try:
        with open(_JSON_PATH) as f:
            old_data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return
    if not old_data:
        return

    conn = _get_conn()
    for name, record in old_data.items():
        existing = conn.execute("SELECT name FROM students WHERE name=?", (name,)).fetchone()
        if existing:
            continue
        conn.execute(
            "INSERT INTO students (name, created_at, topics_mastered, weak_areas, quiz_history) VALUES (?,?,?,?,?)",
            (
                name,
                record.get("created_at", datetime.now().isoformat()),
                json.dumps(record.get("topics_mastered", [])),
                json.dumps(record.get("weak_areas", [])),
                json.dumps(record.get("quiz_history", [])),
            )
        )
        for s in record.get("sessions", []):
            conn.execute(
                "INSERT INTO sessions (student_name, topic, score, action, n_questions, timestamp) VALUES (?,?,?,?,?,?)",
                (name, s.get("topic"), s.get("score"), s.get("action"),
                 s.get("n_questions"), s.get("timestamp", datetime.now().isoformat()))
            )
    conn.commit()
    conn.close()
    # rename old file so we don't migrate again
    _JSON_PATH.rename(_JSON_PATH.with_suffix(".json.migrated"))


_migrate_from_json()


def list_students() -> list[str]:
    conn = _get_conn()
    rows = conn.execute("SELECT name FROM students ORDER BY name").fetchall()
    conn.close()
    return [r["name"] for r in rows]


def load_student(name: str) -> dict:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM students WHERE name=?", (name,)).fetchone()
    if not row:
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO students (name, created_at) VALUES (?, ?)",
            (name, now)
        )
        conn.commit()
        conn.close()
        return {
            "name": name,
            "created_at": now,
            "topics_mastered": [],
            "weak_areas": [],
            "quiz_history": [],
            "sessions": [],
        }

    sessions = conn.execute(
        "SELECT topic, score, action, n_questions, timestamp FROM sessions WHERE student_name=? ORDER BY timestamp",
        (name,)
    ).fetchall()
    conn.close()

    return {
        "name": row["name"],
        "created_at": row["created_at"],
        "topics_mastered": json.loads(row["topics_mastered"]),
        "weak_areas": json.loads(row["weak_areas"]),
        "quiz_history": json.loads(row["quiz_history"]),
        "sessions": [dict(s) for s in sessions],
    }


def save_student(name: str, profile: dict):
    conn = _get_conn()
    conn.execute(
        "UPDATE students SET topics_mastered=?, weak_areas=?, quiz_history=? WHERE name=?",
        (
            json.dumps(profile.get("topics_mastered", [])),
            json.dumps(profile.get("weak_areas", [])),
            json.dumps(profile.get("quiz_history", [])),
            name,
        )
    )
    conn.commit()
    conn.close()


def add_session(name: str, session: dict):
    ts = datetime.now().isoformat()
    conn = _get_conn()
    conn.execute(
        "INSERT INTO sessions (student_name, topic, score, action, n_questions, timestamp) VALUES (?,?,?,?,?,?)",
        (name, session.get("topic"), session.get("score"), session.get("action"),
         session.get("n_questions"), ts)
    )
    conn.commit()
    conn.close()


def delete_student(name: str):
    conn = _get_conn()
    conn.execute("DELETE FROM sessions WHERE student_name=?", (name,))
    conn.execute("DELETE FROM students WHERE name=?", (name,))
    conn.commit()
    conn.close()


def get_all_stats() -> list[dict]:
    """Get summary stats for all students (for pilot study / peer comparison)."""
    conn = _get_conn()
    rows = conn.execute("""
        SELECT s.name, s.topics_mastered, s.weak_areas, s.quiz_history,
               COUNT(sess.id) as session_count,
               AVG(sess.score) as avg_score,
               MIN(sess.timestamp) as first_session,
               MAX(sess.timestamp) as last_session
        FROM students s
        LEFT JOIN sessions sess ON s.name = sess.student_name
        GROUP BY s.name
        ORDER BY avg_score DESC
    """).fetchall()
    conn.close()
    return [
        {
            "name": r["name"],
            "topics_mastered": len(json.loads(r["topics_mastered"])),
            "weak_areas": len(json.loads(r["weak_areas"])),
            "quizzes": len(json.loads(r["quiz_history"])),
            "sessions": r["session_count"],
            "avg_score": r["avg_score"] or 0,
            "first_session": r["first_session"],
            "last_session": r["last_session"],
        }
        for r in rows
    ]

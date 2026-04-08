# storage.py
# Save and load student data to a JSON file
# Simple persistent storage so the agent remembers students across sessions
# Haofei Sun - CSE 5360

import json
import os
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
STUDENTS_FILE = DATA_DIR / "students.json"


def _load_all() -> dict:
    if not STUDENTS_FILE.exists():
        return {}
    try:
        with open(STUDENTS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_all(data: dict):
    with open(STUDENTS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def list_students() -> list[str]:
    """Return all student names we have on record."""
    return sorted(_load_all().keys())


def load_student(name: str) -> dict:
    """Load one student's profile and history. Returns empty record if new."""
    data = _load_all()
    if name not in data:
        data[name] = {
            "name": name,
            "created_at": datetime.now().isoformat(),
            "topics_mastered": [],
            "weak_areas": [],
            "quiz_history": [],
            "sessions": [],
        }
        _save_all(data)
    return data[name]


def save_student(name: str, profile: dict):
    """Write the student record back to disk."""
    data = _load_all()
    data[name] = profile
    _save_all(data)


def add_session(name: str, session: dict):
    """Append one completed session to the student's history."""
    student = load_student(name)
    session["timestamp"] = datetime.now().isoformat()
    student["sessions"].append(session)
    save_student(name, student)


def delete_student(name: str):
    data = _load_all()
    if name in data:
        del data[name]
        _save_all(data)

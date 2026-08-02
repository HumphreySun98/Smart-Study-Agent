# anki_export.py
# Export the question bank as an Anki .apkg deck (via genanki).
# Cards carry an "SmartStudy" tag plus their topic, so FSRS-enabled Anki
# picks them up like any other deck.
# Haofei Sun - CSE 5360

import hashlib
import html
import tempfile
from pathlib import Path

try:
    import genanki
    HAS_GENANKI = True
except ImportError:
    HAS_GENANKI = False


# stable IDs so re-imports update instead of duplicating
_MODEL_ID = 1607392319
_DECK_BASE_ID = 2059400110

_CSS = """
.card { font-family: -apple-system, 'Segoe UI', sans-serif; font-size: 18px;
        text-align: left; color: #1e293b; background: #f8fafc; padding: 18px; }
.topic { font-size: 13px; letter-spacing: 1px; text-transform: uppercase;
         color: #6366f1; font-weight: 700; margin-bottom: 10px; }
.choices { margin-top: 12px; line-height: 1.7; }
.answer { font-weight: 700; color: #16a34a; font-size: 20px; }
.explanation { margin-top: 10px; color: #475569; font-style: italic; }
"""


def _mcq_model():
    return genanki.Model(
        _MODEL_ID,
        "SmartStudy MCQ",
        fields=[
            {"name": "Topic"},
            {"name": "Question"},
            {"name": "Choices"},
            {"name": "Answer"},
            {"name": "Explanation"},
        ],
        templates=[
            {
                "name": "MCQ Card",
                "qfmt": (
                    '<div class="topic">{{Topic}}</div>'
                    "<b>{{Question}}</b>"
                    '<div class="choices">{{Choices}}</div>'
                ),
                "afmt": (
                    '{{FrontSide}}<hr id="answer">'
                    '<div class="answer">✓ {{Answer}}</div>'
                    '<div class="explanation">{{Explanation}}</div>'
                ),
            }
        ],
        css=_CSS,
    )


def _deck_id(student_name: str) -> int:
    digest = hashlib.md5(student_name.encode()).hexdigest()
    return _DECK_BASE_ID + int(digest[:6], 16)


def build_deck(student_name: str, questions: list[dict]) -> bytes:
    """Build an .apkg from question dicts and return the file bytes.
    Each dict: {topic, question, choices (list), correct_answer, explanation}."""
    if not HAS_GENANKI:
        raise ImportError("Anki export requires `pip install genanki`")
    if not questions:
        raise ValueError("Question bank is empty — generate some quizzes first.")

    deck = genanki.Deck(_deck_id(student_name),
                        f"SmartStudy::{student_name}")
    model = _mcq_model()

    for q in questions:
        choices = q.get("choices") or []
        choices_html = "<br>".join(html.escape(c) for c in choices)
        # resolve "B" → full choice text for the back side
        letter = (q.get("correct_answer") or "").strip().upper()[:1]
        answer_text = letter
        for c in choices:
            if c.strip().upper().startswith(f"{letter})"):
                answer_text = c
                break

        topic = q.get("topic", "General")
        note = genanki.Note(
            model=model,
            fields=[
                html.escape(topic),
                html.escape(q.get("question", "")),
                choices_html,
                html.escape(answer_text),
                html.escape(q.get("explanation", "")),
            ],
            tags=["SmartStudy", topic.replace(" ", "_")],
        )
        deck.add_note(note)

    with tempfile.NamedTemporaryFile(suffix=".apkg", delete=False) as tmp:
        genanki.Package(deck).write_to_file(tmp.name)
        data = Path(tmp.name).read_bytes()
    Path(tmp.name).unlink(missing_ok=True)
    return data


def export_student_deck(student_name: str, out_path: str = None) -> str:
    """Convenience: pull the student's question bank from storage and write
    an .apkg next to the data dir (or to out_path). Returns the file path."""
    import storage
    questions = storage.get_question_bank(student_name)
    data = build_deck(student_name, questions)
    if out_path is None:
        out_path = str(Path(storage.DATA_DIR) /
                       f"smartstudy_{student_name.replace(' ', '_')}.apkg")
    Path(out_path).write_bytes(data)
    return out_path

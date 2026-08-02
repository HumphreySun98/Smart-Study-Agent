# spaced_repetition.py
# Review scheduler. Default algorithm is FSRS (via py-fsrs) with an SM-2
# fallback when the package is unavailable. Both replay quiz_history
# statelessly, so no schema change is needed.
# Haofei Sun - CSE 5360

from datetime import datetime, timedelta, timezone

try:
    from fsrs import Scheduler, Card, Rating
    HAS_FSRS = True
except ImportError:
    HAS_FSRS = False


# ---- SM-2 (legacy, kept as fallback) ----

def calculate_next_review(score: float, prev_interval_days: int = 1,
                          prev_easiness: float = 2.5) -> tuple:
    """SM-2 update — returns (next_interval_days, new_easiness)."""
    quality = round(score * 5)

    if quality < 3:
        new_interval = 1   # failed → short interval
    elif prev_interval_days == 1:
        new_interval = 6
    else:
        new_interval = round(prev_interval_days * prev_easiness)

    new_easiness = prev_easiness + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    new_easiness = max(1.3, new_easiness)

    return new_interval, new_easiness


# ---- shared helpers ----

def _parse_ts(ts_str: str) -> datetime | None:
    """ISO timestamp → aware UTC datetime (naive values assumed local)."""
    try:
        dt = datetime.fromisoformat(ts_str)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt.astimezone(timezone.utc)


def _attempts_by_topic(quiz_history: list[dict]) -> dict[str, list[dict]]:
    """Group timestamped attempts per topic, chronological order."""
    by_topic: dict[str, list[dict]] = {}
    for entry in quiz_history:
        topic = entry.get("topic")
        if not topic or not entry.get("timestamp"):
            continue
        by_topic.setdefault(topic, []).append(entry)
    for attempts in by_topic.values():
        attempts.sort(key=lambda e: e.get("timestamp", ""))
    return by_topic


def score_to_rating(score: float):
    """Quiz score → FSRS rating (Again/Hard/Good/Easy)."""
    if score < 0.5:
        return Rating.Again
    if score < 0.7:
        return Rating.Hard
    if score < 0.9:
        return Rating.Good
    return Rating.Easy


# ---- FSRS scheduler ----

def fsrs_schedule(quiz_history: list[dict]) -> list[dict]:
    """Replay each topic's attempts through FSRS. Returns one row per topic:
    topic, last_score, due (datetime), days_overdue, retrievability,
    stability, difficulty, last_seen. Rows are NOT filtered by due date."""
    if not HAS_FSRS:
        raise ImportError("pip install fsrs")

    scheduler = Scheduler()
    now = datetime.now(timezone.utc)
    rows = []

    for topic, attempts in _attempts_by_topic(quiz_history).items():
        card = Card()
        last_score, last_dt = 0.0, None
        for entry in attempts:
            dt = _parse_ts(entry["timestamp"])
            if dt is None:
                continue
            # FSRS requires monotonically increasing review times
            if last_dt is not None and dt <= last_dt:
                dt = last_dt + timedelta(seconds=1)
            card, _ = scheduler.review_card(card, score_to_rating(entry.get("score", 0.0)), dt)
            last_score, last_dt = entry.get("score", 0.0), dt

        if last_dt is None:
            continue

        retrievability = scheduler.get_card_retrievability(card, now)
        rows.append({
            "topic": topic,
            "last_score": last_score,
            "due": card.due,
            "days_overdue": (now - card.due).days,
            "retrievability": round(float(retrievability), 3),
            "stability": round(float(card.stability or 0.0), 2),
            "difficulty": round(float(card.difficulty or 0.0), 2),
            "last_seen": last_dt.astimezone().strftime("%Y-%m-%d"),
        })

    # weakest memories first
    rows.sort(key=lambda r: r["retrievability"])
    return rows


# ---- legacy SM-2 queue (fallback path) ----

def _sm2_review_queue(quiz_history: list[dict]) -> list[dict]:
    by_topic = _attempts_by_topic(quiz_history)
    queue = []
    now = datetime.now(timezone.utc)
    for topic, attempts in by_topic.items():
        entry = attempts[-1]
        score = entry.get("score", 0)
        last_seen = _parse_ts(entry["timestamp"])
        if last_seen is None:
            continue

        interval, _ = calculate_next_review(score)
        due_date = last_seen + timedelta(days=interval)
        days_until_due = (due_date - now).days

        if days_until_due <= 0:
            queue.append({
                "topic": topic,
                "last_score": score,
                "days_overdue": -days_until_due,
                "last_seen": last_seen.astimezone().strftime("%Y-%m-%d"),
            })

    queue.sort(key=lambda x: -x["days_overdue"])
    return queue


# ---- public API ----

ALGORITHM = "FSRS" if HAS_FSRS else "SM-2"


def get_review_queue(quiz_history: list[dict]) -> list[dict]:
    """Topics due for review now. FSRS when available, else SM-2.
    Backward-compatible keys: topic, last_score, days_overdue, last_seen."""
    if not quiz_history:
        return []
    if HAS_FSRS:
        now = datetime.now(timezone.utc)
        return [r for r in fsrs_schedule(quiz_history) if r["due"] <= now]
    return _sm2_review_queue(quiz_history)


def get_full_schedule(quiz_history: list[dict]) -> list[dict]:
    """All studied topics with next-due info (FSRS only; [] otherwise)."""
    if not quiz_history or not HAS_FSRS:
        return []
    return fsrs_schedule(quiz_history)

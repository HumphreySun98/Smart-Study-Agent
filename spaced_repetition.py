# spaced_repetition.py
# SM-2 inspired spaced repetition scheduler
# Tells the student which topics to review today based on past performance
# Haofei Sun - CSE 5360

from datetime import datetime, timedelta


def calculate_next_review(score: float, prev_interval_days: int = 1,
                          prev_easiness: float = 2.5) -> tuple:
    """
    SM-2 style update.
    Returns (next_interval_in_days, new_easiness_factor).
    """
    # quality 0-5 based on score
    quality = round(score * 5)

    if quality < 3:
        # failed - reset to short interval
        new_interval = 1
    elif prev_interval_days == 1:
        new_interval = 6
    else:
        new_interval = round(prev_interval_days * prev_easiness)

    # update easiness factor
    new_easiness = prev_easiness + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    new_easiness = max(1.3, new_easiness)

    return new_interval, new_easiness


def get_review_queue(quiz_history: list[dict]) -> list[dict]:
    """
    Look through history and find topics that are due for review today.
    Returns list of {topic, last_score, days_overdue}.
    """
    if not quiz_history:
        return []

    # group by topic, take most recent attempt
    by_topic = {}
    for entry in quiz_history:
        topic = entry.get("topic")
        if topic not in by_topic:
            by_topic[topic] = entry
        else:
            existing_ts = by_topic[topic].get("timestamp", "")
            current_ts = entry.get("timestamp", "")
            if current_ts > existing_ts:
                by_topic[topic] = entry

    queue = []
    now = datetime.now()
    for topic, entry in by_topic.items():
        score = entry.get("score", 0)
        ts_str = entry.get("timestamp")
        if not ts_str:
            continue
        try:
            last_seen = datetime.fromisoformat(ts_str)
        except ValueError:
            continue

        interval, _ = calculate_next_review(score)
        due_date = last_seen + timedelta(days=interval)
        days_until_due = (due_date - now).days

        if days_until_due <= 0:
            queue.append({
                "topic": topic,
                "last_score": score,
                "days_overdue": -days_until_due,
                "last_seen": last_seen.strftime("%Y-%m-%d"),
            })

    # sort by most overdue first
    queue.sort(key=lambda x: -x["days_overdue"])
    return queue

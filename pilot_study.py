# pilot_study.py
# Aggregates DB rows into pilot-study metrics and a printable report.
# Haofei Sun - CSE 5360

import statistics
from datetime import datetime
import storage


def collect_metrics() -> dict:
    """Per-class score / mastery / session totals."""
    stats = storage.get_all_stats()
    if not stats:
        return {"n_students": 0}

    scores = [s["avg_score"] for s in stats if s["avg_score"]]
    mastered_counts = [s["topics_mastered"] for s in stats]
    session_counts = [s["sessions"] for s in stats]

    return {
        "n_students": len(stats),
        "total_sessions": sum(session_counts),
        "avg_score_mean": statistics.mean(scores) if scores else 0,
        "avg_score_std": statistics.stdev(scores) if len(scores) > 1 else 0,
        "avg_topics_mastered": statistics.mean(mastered_counts) if mastered_counts else 0,
        "avg_sessions_per_student": statistics.mean(session_counts) if session_counts else 0,
        "students": stats,
    }


def engagement_analysis() -> dict:
    """Active vs one-time vs inactive student counts and retention rate."""
    stats = storage.get_all_stats()
    if not stats:
        return {}

    active = [s for s in stats if s["sessions"] >= 2]
    one_time = [s for s in stats if s["sessions"] == 1]
    inactive = [s for s in stats if s["sessions"] == 0]

    return {
        "total_students": len(stats),
        "active_students": len(active),
        "one_time_students": len(one_time),
        "inactive_students": len(inactive),
        "retention_rate": len(active) / len(stats) if stats else 0,
    }


def mastery_progression() -> list[dict]:
    """First-half vs second-half quiz averages, per student."""
    results = []
    for name in storage.list_students():
        record = storage.load_student(name)
        history = record.get("quiz_history", [])
        if len(history) < 2:
            continue

        scores = [h["score"] for h in history]
        first_half = scores[:len(scores)//2]
        second_half = scores[len(scores)//2:]

        results.append({
            "student": name,
            "n_quizzes": len(scores),
            "first_half_avg": statistics.mean(first_half),
            "second_half_avg": statistics.mean(second_half),
            "improvement": statistics.mean(second_half) - statistics.mean(first_half),
            "topics_mastered": len(record.get("topics_mastered", [])),
        })

    return results


def generate_report() -> str:
    """Plain-text pilot study report."""
    metrics = collect_metrics()
    engagement = engagement_analysis()
    progression = mastery_progression()

    if metrics["n_students"] == 0:
        return "No pilot study data available yet. Students need to complete study sessions first."

    lines = [
        "=" * 60,
        "SMARTSTUDY AGENT — PILOT STUDY REPORT",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 60,
        "",
        "1. PARTICIPATION",
        f"   Total students:    {metrics['n_students']}",
        f"   Total sessions:    {metrics['total_sessions']}",
        f"   Avg sessions/user: {metrics['avg_sessions_per_student']:.1f}",
        "",
        "2. ENGAGEMENT",
        f"   Active (2+ sessions): {engagement.get('active_students', 0)}",
        f"   One-time users:       {engagement.get('one_time_students', 0)}",
        f"   Retention rate:       {engagement.get('retention_rate', 0):.0%}",
        "",
        "3. PERFORMANCE",
        f"   Avg quiz score:       {metrics['avg_score_mean']:.1%} (±{metrics['avg_score_std']:.1%})",
        f"   Avg topics mastered:  {metrics['avg_topics_mastered']:.1f}",
        "",
    ]

    if progression:
        avg_improvement = statistics.mean([p["improvement"] for p in progression])
        improved = sum(1 for p in progression if p["improvement"] > 0)
        lines += [
            "4. LEARNING PROGRESSION",
            f"   Students with 2+ quizzes: {len(progression)}",
            f"   Avg score improvement:    {avg_improvement:+.1%}",
            f"   Students who improved:    {improved}/{len(progression)} ({improved/len(progression):.0%})",
            "",
            "   Per-student breakdown:",
        ]
        for p in progression:
            lines.append(
                f"     {p['student']}: {p['first_half_avg']:.0%} → {p['second_half_avg']:.0%} "
                f"({p['improvement']:+.0%}), mastered {p['topics_mastered']} topics"
            )
        lines.append("")

    lines += [
        "5. CONCLUSION",
        f"   The SmartStudy Agent was tested with {metrics['n_students']} student(s).",
    ]
    if progression:
        avg_imp = statistics.mean([p["improvement"] for p in progression])
        if avg_imp > 0:
            lines.append(f"   Average score improvement of {avg_imp:+.1%} observed across sessions,")
            lines.append("   suggesting the adaptive policy is effective at guiding learning.")
        else:
            lines.append("   No significant improvement detected yet — more sessions recommended.")
    else:
        lines.append("   Insufficient data for progression analysis — need more quiz attempts.")

    lines += ["", "=" * 60]
    return "\n".join(lines)

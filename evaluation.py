# evaluation.py
# Quantitative evaluation of the agent vs a baseline
# Baseline = random topic selection, no adaptive policy
# Metric = average quiz score after N sessions on simulated students
# Haofei Sun - CSE 5360

import random
import statistics


def simulate_student(initial_skill: float = 0.5, learning_rate: float = 0.08):
    """
    Simulated student with a hidden 'skill' value per topic.
    Skill goes up when they study, down slowly otherwise.
    """
    return {
        "skills": {},   # topic -> skill (0..1)
        "initial": initial_skill,
        "lr": learning_rate,
    }


def simulate_quiz(student: dict, topic: str, action: str = "advance") -> float:
    """
    Run one quiz attempt. Returns the score.
    Skill improves more if the action is reinforce/review.
    """
    skill = student["skills"].get(topic, student["initial"])
    # add some noise
    score = max(0.0, min(1.0, skill + random.gauss(0, 0.15)))

    # studying improves the skill (reinforce/review boost more)
    boost = student["lr"]
    if action == "reinforce":
        boost *= 1.5
    elif action == "review":
        boost *= 2.0
    student["skills"][topic] = min(1.0, skill + boost)
    return score


def run_baseline(topics: list[str], n_sessions: int = 20) -> dict:
    """Random topic selection, always 'advance'."""
    student = simulate_student()
    scores = []
    for _ in range(n_sessions):
        topic = random.choice(topics)
        score = simulate_quiz(student, topic, action="advance")
        scores.append(score)
    return {
        "method": "baseline",
        "scores": scores,
        "avg_score": statistics.mean(scores),
        "final_score": scores[-1],
    }


def run_adaptive(topics: list[str], n_sessions: int = 20) -> dict:
    """
    Adaptive: pick the weakest topic, use threshold-based action.
    """
    student = simulate_student()
    scores = []
    history = {}

    for _ in range(n_sessions):
        # pick the topic with lowest skill (or new topic)
        weak_topics = [t for t in topics if t not in history or history[t] < 0.7]
        topic = min(weak_topics, key=lambda t: history.get(t, 0)) if weak_topics else random.choice(topics)

        prev_score = history.get(topic, 0)
        if prev_score < 0.5:
            action = "review"
        elif prev_score < 0.7:
            action = "reinforce"
        else:
            action = "advance"

        score = simulate_quiz(student, topic, action=action)
        history[topic] = score
        scores.append(score)

    return {
        "method": "adaptive",
        "scores": scores,
        "avg_score": statistics.mean(scores),
        "final_score": scores[-1],
    }


def compare(n_runs: int = 30, n_sessions: int = 20) -> dict:
    """
    Run both methods n_runs times to get statistical comparison.
    Returns mean and std of average scores.
    """
    topics = ["Supervised", "Unsupervised", "Neural Nets",
              "Overfitting", "Backprop", "Evaluation"]

    baseline_results = [run_baseline(topics, n_sessions)["avg_score"] for _ in range(n_runs)]
    adaptive_results = [run_adaptive(topics, n_sessions)["avg_score"] for _ in range(n_runs)]

    return {
        "baseline": {
            "mean": statistics.mean(baseline_results),
            "std": statistics.stdev(baseline_results),
            "all": baseline_results,
        },
        "adaptive": {
            "mean": statistics.mean(adaptive_results),
            "std": statistics.stdev(adaptive_results),
            "all": adaptive_results,
        },
        "improvement_pct": (
            (statistics.mean(adaptive_results) - statistics.mean(baseline_results))
            / statistics.mean(baseline_results) * 100
        ),
    }

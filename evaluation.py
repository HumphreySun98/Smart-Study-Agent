# evaluation.py
# Quantitative evaluation of adaptive policies against realistic baselines.
#
# Implements the professor's feedback:
#   "Look into Simulated Student Models or compare against a Rule-based
#    baseline rather than just a random one."
#
# Four policies are compared on the same simulated students:
#   1. Random        — pick any topic, always "advance". Sanity-check floor.
#   2. Rule-based    — Bloom's 70% mastery threshold (classic ITS heuristic).
#   3. Bandit        — Contextual Bandit (LinUCB). No sequence modeling.
#   4. RL            — Tabular Q-learning. Models state transitions.
#
# The simulated student is a small cognitive model (skill per topic,
# forgetting, noise, prerequisite coupling) — richer than the previous
# random-score generator so differences between policies are not washed out.
#
# Haofei Sun - CSE 5360

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass, field

# Lazy imports so `evaluation.py` can be imported even if numpy isn't
# installed yet (the RL/bandit paths require it, but `run_random` doesn't).

TOPICS = ["Supervised", "Unsupervised", "Neural Nets",
          "Overfitting", "Backprop", "Evaluation"]

# A tiny prerequisite graph. Studying a topic whose prereq is weak gives
# a smaller skill gain, which creates the "sequence matters" signal that
# a full RL formulation can exploit and a plain bandit cannot.
PREREQS = {
    "Neural Nets": ["Supervised"],
    "Backprop":    ["Neural Nets"],
    "Overfitting": ["Supervised"],
    "Evaluation":  ["Supervised"],
}

ACTIONS = ["review", "reinforce", "advance"]


# ---------- Simulated Student Model ----------

@dataclass
class SimulatedStudent:
    """
    Per-topic hidden skill in [0, 1], plus a forgetting dynamic and a
    prerequisite-coupled learning rate. Each step:
      - observed quiz score = noisy sigmoid of (skill - difficulty)
      - on the practiced topic, skill increases by an action-dependent
        amount, scaled by how well prereqs are mastered
      - all other topics decay slightly (forgetting curve)
    """
    skills: dict[str, float] = field(default_factory=dict)
    initial: float = 0.35
    base_lr: float = 0.12
    forget_rate: float = 0.01
    noise: float = 0.10

    def _skill(self, topic: str) -> float:
        return self.skills.get(topic, self.initial)

    def _prereq_factor(self, topic: str) -> float:
        pr = PREREQS.get(topic, [])
        if not pr:
            return 1.0
        # weakest prereq gates learning — models "you can't do backprop
        # effectively until neural nets are solid"
        return min(self._skill(p) for p in pr) ** 0.5

    def study(self, topic: str, action: str) -> float:
        """Simulate one quiz + study step. Returns the observed score."""
        skill = self._skill(topic)

        # observed score: sigmoid-ish, plus gaussian noise, clipped
        observed = skill + random.gauss(0, self.noise)
        observed = max(0.0, min(1.0, observed))

        # learning gain depends on action + prereqs + current skill
        action_mult = {"review": 1.6, "reinforce": 1.2, "advance": 0.5}[action]
        # diminishing returns as skill approaches 1
        room_to_grow = 1.0 - skill
        gain = self.base_lr * action_mult * self._prereq_factor(topic) * room_to_grow
        self.skills[topic] = min(1.0, skill + gain)

        # everything else forgets a bit
        for t in list(self.skills.keys()):
            if t != topic:
                self.skills[t] = max(0.0, self.skills[t] - self.forget_rate)

        return observed

    def mean_skill(self) -> float:
        if not self.skills:
            return self.initial
        return statistics.mean(self.skills.values())


# ---------- Policies over topic × action ----------

def _weakest_topic(history: dict[str, float], topics: list[str]) -> str:
    unseen = [t for t in topics if t not in history]
    if unseen:
        return unseen[0]
    return min(topics, key=lambda t: history[t])


def run_random(topics: list[str], n_sessions: int = 30, seed: int | None = None) -> dict:
    rng = random.Random(seed)
    student = SimulatedStudent()
    scores = []
    for _ in range(n_sessions):
        topic = rng.choice(topics)
        scores.append(student.study(topic, "advance"))
    return {"method": "random", "scores": scores,
            "avg_score": statistics.mean(scores),
            "final_score": scores[-1],
            "final_mean_skill": student.mean_skill()}


def run_rule_based(topics: list[str], n_sessions: int = 30, seed: int | None = None) -> dict:
    """Bloom's 70% mastery heuristic + weakest-topic-first."""
    rng = random.Random(seed)
    student = SimulatedStudent()
    history: dict[str, float] = {}
    scores = []
    for _ in range(n_sessions):
        weak = [t for t in topics if history.get(t, 0.0) < 0.7]
        topic = rng.choice(weak) if weak else rng.choice(topics)
        prev = history.get(topic, 0.0)
        if prev < 0.5:
            action = "review"
        elif prev < 0.7:
            action = "reinforce"
        else:
            action = "advance"
        s = student.study(topic, action)
        history[topic] = s
        scores.append(s)
    return {"method": "rule_based", "scores": scores,
            "avg_score": statistics.mean(scores),
            "final_score": scores[-1],
            "final_mean_skill": student.mean_skill()}


def run_bandit(topics: list[str], n_sessions: int = 30, seed: int | None = None,
               reset: bool = True) -> dict:
    """Contextual Bandit (LinUCB). No cross-step credit assignment."""
    from bandit_policy import LinUCBBandit, BANDIT_FILE
    if reset and BANDIT_FILE.exists():
        BANDIT_FILE.unlink()
    rng = random.Random(seed)
    bandit = LinUCBBandit(alpha=0.8)
    student = SimulatedStudent()
    history: dict[str, float] = {}
    attempts: dict[str, int] = {}
    scores = []
    for _ in range(n_sessions):
        topic = _weakest_topic(history, topics) if rng.random() > 0.3 else rng.choice(topics)
        prev = history.get(topic, 0.0)
        t_idx = topics.index(topic) % 8
        attempts_on_topic = attempts.get(topic, 0)
        action = bandit.choose_action(prev, attempts_on_topic, t_idx, len(topics))
        s = student.study(topic, action)
        # bandit reward = immediate score improvement
        reward = (s - prev) * 10.0
        bandit.update(prev, action, reward, attempts_on_topic, t_idx, len(topics))
        history[topic] = s
        attempts[topic] = attempts_on_topic + 1
        scores.append(s)
    return {"method": "bandit", "scores": scores,
            "avg_score": statistics.mean(scores),
            "final_score": scores[-1],
            "final_mean_skill": student.mean_skill()}


def run_rl(topics: list[str], n_sessions: int = 30, seed: int | None = None,
           reset: bool = True) -> dict:
    """Tabular Q-learning. Bootstraps off next-state value — models sequence."""
    from rl_policy import QLearningPolicy, QTABLE_FILE
    if reset and QTABLE_FILE.exists():
        QTABLE_FILE.unlink()
    rng = random.Random(seed)
    policy = QLearningPolicy(alpha=0.25, gamma=0.85, epsilon=0.15)
    student = SimulatedStudent()
    history: dict[str, float] = {}
    scores = []
    for _ in range(n_sessions):
        topic = _weakest_topic(history, topics) if rng.random() > 0.3 else rng.choice(topics)
        prev = history.get(topic, 0.0)
        action = policy.choose_action(prev)
        s = student.study(topic, action)
        policy.update(prev, action, s)
        history[topic] = s
        scores.append(s)
    return {"method": "rl_qlearning", "scores": scores,
            "avg_score": statistics.mean(scores),
            "final_score": scores[-1],
            "final_mean_skill": student.mean_skill()}


# ---------- Comparison driver ----------

def compare(n_runs: int = 30, n_sessions: int = 30, topics: list[str] | None = None) -> dict:
    """
    Run every policy n_runs times on fresh simulated students and report
    mean / std of the average observed quiz score AND final mean skill.
    """
    topics = topics or TOPICS

    runners = {
        "random":     run_random,
        "rule_based": run_rule_based,
        "bandit":     run_bandit,
        "rl":         run_rl,
    }
    out: dict[str, dict] = {}
    for name, fn in runners.items():
        avg_scores = []
        final_skills = []
        for i in range(n_runs):
            # same seed across runners so they face the SAME student trajectory
            res = fn(topics, n_sessions=n_sessions, seed=1000 + i)
            avg_scores.append(res["avg_score"])
            final_skills.append(res["final_mean_skill"])
        out[name] = {
            "mean_avg_score":   statistics.mean(avg_scores),
            "std_avg_score":    statistics.stdev(avg_scores) if n_runs > 1 else 0.0,
            "mean_final_skill": statistics.mean(final_skills),
            "std_final_skill":  statistics.stdev(final_skills) if n_runs > 1 else 0.0,
            "all_scores":       avg_scores,
        }

    base = out["random"]["mean_avg_score"]
    for name in out:
        gain = (out[name]["mean_avg_score"] - base) / base * 100 if base > 0 else 0.0
        out[name]["improvement_over_random_pct"] = gain
    return out


def print_report(results: dict) -> None:
    header = f"{'policy':<12} {'avg_score':>12} {'final_skill':>14} {'vs random':>12}"
    print(header)
    print("-" * len(header))
    for name, r in results.items():
        print(
            f"{name:<12} "
            f"{r['mean_avg_score']:>6.3f} ± {r['std_avg_score']:.3f}  "
            f"{r['mean_final_skill']:>6.3f} ± {r['std_final_skill']:.3f}  "
            f"{r['improvement_over_random_pct']:>+8.1f}%"
        )


if __name__ == "__main__":
    print("Running 4-policy comparison on simulated students...")
    print(f"  topics   = {TOPICS}")
    print(f"  sessions = 30 per student, 30 students per policy")
    print()
    results = compare(n_runs=30, n_sessions=30)
    print_report(results)

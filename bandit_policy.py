# bandit_policy.py
# Contextual Bandit policy (LinUCB) — alternative to Q-learning.
# Added in response to feedback: "If state transitions are not significant,
# Contextual Bandits are more sample-efficient than full RL."
#
# Key difference from rl_policy.QLearningPolicy:
#   - Bandit: treats each quiz as an independent decision given the context.
#             No discount factor, no next-state bootstrap. More sample-efficient.
#   - Q-learning: models the sequence — action now affects future mastery state.
#
# We keep BOTH so the evaluation script can compare them fairly on the same
# simulated students, and so the project explicitly demonstrates the trade-off.
#
# Haofei Sun - CSE 5360

import json
import math
import random
from pathlib import Path

import numpy as np

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
BANDIT_FILE = DATA_DIR / "bandit.json"

ACTIONS = ["review", "reinforce", "advance"]


def _context_vector(score: float, attempts_on_topic: int, topic_idx: int, n_topics: int) -> np.ndarray:
    """
    Build a feature vector describing the current decision context.
    Bandits condition on context but don't model transitions between contexts.
    """
    # bucketed score (one-hot, 5 buckets)
    buckets = np.zeros(5)
    if score < 0.3:
        buckets[0] = 1
    elif score < 0.5:
        buckets[1] = 1
    elif score < 0.7:
        buckets[2] = 1
    elif score < 0.9:
        buckets[3] = 1
    else:
        buckets[4] = 1

    # topic one-hot (bounded, pad/truncate to 8)
    topic_oh = np.zeros(8)
    if 0 <= topic_idx < 8:
        topic_oh[topic_idx] = 1

    # continuous features
    extras = np.array([
        score,
        math.log1p(max(0, attempts_on_topic)) / 3.0,  # saturates around 20 attempts
        1.0,  # bias
    ])

    return np.concatenate([buckets, topic_oh, extras])


FEATURE_DIM = 5 + 8 + 3  # = 16


class LinUCBBandit:
    """
    LinUCB contextual bandit with one linear model per action.
    Reward model:  r | x, a  ~  N(theta_a^T x, sigma^2)
    Action rule:   a = argmax_a ( theta_a^T x  +  alpha * sqrt(x^T A_a^{-1} x) )

    The exploration bonus shrinks as each action accumulates data, so
    the policy converges to pure exploitation — unlike epsilon-greedy,
    which keeps exploring forever at rate epsilon.
    """

    def __init__(self, alpha: float = 0.8, d: int = FEATURE_DIM):
        self.alpha = alpha
        self.d = d
        self.A = {a: np.eye(d) for a in ACTIONS}       # d x d per action
        self.b = {a: np.zeros(d) for a in ACTIONS}     # d per action
        self.n_pulls = {a: 0 for a in ACTIONS}
        self._load()

    # --- persistence ---

    def _load(self):
        if not BANDIT_FILE.exists():
            return
        try:
            data = json.loads(BANDIT_FILE.read_text())
            for a in ACTIONS:
                self.A[a] = np.array(data["A"][a])
                self.b[a] = np.array(data["b"][a])
                self.n_pulls[a] = data["n_pulls"][a]
        except (json.JSONDecodeError, IOError, KeyError, ValueError):
            pass

    def save(self):
        payload = {
            "A": {a: self.A[a].tolist() for a in ACTIONS},
            "b": {a: self.b[a].tolist() for a in ACTIONS},
            "n_pulls": self.n_pulls,
        }
        BANDIT_FILE.write_text(json.dumps(payload, indent=2))

    # --- decision + learning ---

    def _theta(self, a: str) -> np.ndarray:
        return np.linalg.solve(self.A[a], self.b[a])

    def choose_action(self, score: float, attempts_on_topic: int = 0,
                      topic_idx: int = 0, n_topics: int = 8) -> str:
        x = _context_vector(score, attempts_on_topic, topic_idx, n_topics)
        best_a, best_ucb = ACTIONS[0], -1e18
        for a in ACTIONS:
            A_inv = np.linalg.inv(self.A[a])
            theta = A_inv @ self.b[a]
            mean = float(theta @ x)
            bonus = self.alpha * float(math.sqrt(x @ A_inv @ x))
            ucb = mean + bonus
            if ucb > best_ucb:
                best_ucb, best_a = ucb, a
        return best_a

    def update(self, score: float, action: str, reward: float,
               attempts_on_topic: int = 0, topic_idx: int = 0, n_topics: int = 8):
        x = _context_vector(score, attempts_on_topic, topic_idx, n_topics)
        self.A[action] += np.outer(x, x)
        self.b[action] += reward * x
        self.n_pulls[action] += 1
        self.save()

    def policy_summary(self) -> dict:
        """Greedy action in each score bucket, at a neutral topic context."""
        summary = {}
        for label, s in [("very_low", 0.15), ("low", 0.4), ("medium", 0.6),
                         ("high", 0.8), ("very_high", 0.95)]:
            x = _context_vector(s, 3, 0, 8)
            best_a, best_q = ACTIONS[0], -1e18
            for a in ACTIONS:
                theta = self._theta(a)
                q = float(theta @ x)
                if q > best_q:
                    best_q, best_a = q, a
            summary[label] = best_a
        return summary


class EpsilonGreedyBandit:
    """
    Simpler baseline bandit — constant-epsilon exploration over a
    coarse state discretization. Useful to show that LinUCB's context
    features actually buy something over a tabular bandit.
    """

    def __init__(self, epsilon: float = 0.15):
        self.epsilon = epsilon
        self.counts = {}   # (state, action) -> n
        self.values = {}   # (state, action) -> mean reward

    @staticmethod
    def _state(score: float) -> str:
        if score < 0.3: return "very_low"
        if score < 0.5: return "low"
        if score < 0.7: return "medium"
        if score < 0.9: return "high"
        return "very_high"

    def choose_action(self, score: float, **_) -> str:
        if random.random() < self.epsilon:
            return random.choice(ACTIONS)
        s = self._state(score)
        best_a, best_v = ACTIONS[0], -1e18
        for a in ACTIONS:
            v = self.values.get((s, a), 0.0)
            if v > best_v:
                best_v, best_a = v, a
        return best_a

    def update(self, score: float, action: str, reward: float, **_):
        s = self._state(score)
        key = (s, action)
        n = self.counts.get(key, 0) + 1
        old = self.values.get(key, 0.0)
        self.values[key] = old + (reward - old) / n
        self.counts[key] = n

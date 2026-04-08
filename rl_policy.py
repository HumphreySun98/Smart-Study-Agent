# rl_policy.py
# Q-learning based adaptive policy
# Replaces the heuristic 70% threshold with a learned policy
# State = mastery bucket, Action = advance/reinforce/review
# Haofei Sun - CSE 5360

import json
import random
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
QTABLE_FILE = DATA_DIR / "qtable.json"


# discretize the score into 5 buckets so the state space is small
def score_to_state(score: float) -> str:
    if score < 0.3:
        return "very_low"
    if score < 0.5:
        return "low"
    if score < 0.7:
        return "medium"
    if score < 0.9:
        return "high"
    return "very_high"


ACTIONS = ["review", "reinforce", "advance"]


class QLearningPolicy:
    """
    Tabular Q-learning agent.
    State: discretized quiz score bucket
    Action: review / reinforce / advance
    Reward: +1 if next quiz score improves, -1 if it drops, 0 if same
    """

    def __init__(self, alpha=0.2, gamma=0.8, epsilon=0.15):
        self.alpha = alpha   # learning rate
        self.gamma = gamma   # discount factor
        self.epsilon = epsilon   # exploration rate
        self.q = self._load()

    def _load(self) -> dict:
        if QTABLE_FILE.exists():
            try:
                with open(QTABLE_FILE) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        # initialize Q-table with small random values
        return {
            state: {a: random.uniform(0, 0.1) for a in ACTIONS}
            for state in ["very_low", "low", "medium", "high", "very_high"]
        }

    def save(self):
        with open(QTABLE_FILE, "w") as f:
            json.dump(self.q, f, indent=2)

    def choose_action(self, score: float) -> str:
        state = score_to_state(score)
        # epsilon-greedy
        if random.random() < self.epsilon:
            return random.choice(ACTIONS)
        return max(self.q[state], key=self.q[state].get)

    def update(self, prev_score: float, action: str, new_score: float):
        """Update Q-value based on score change."""
        state = score_to_state(prev_score)
        next_state = score_to_state(new_score)

        # reward is the score delta (scaled)
        reward = (new_score - prev_score) * 10

        old_q = self.q[state][action]
        future_q = max(self.q[next_state].values())
        new_q = old_q + self.alpha * (reward + self.gamma * future_q - old_q)
        self.q[state][action] = new_q
        self.save()

    def policy_summary(self) -> dict:
        """Return the best action for each state."""
        return {
            state: max(actions, key=actions.get)
            for state, actions in self.q.items()
        }

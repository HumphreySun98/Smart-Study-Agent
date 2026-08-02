# experiments/scheduler_comparison.py
# Does the review *scheduler* matter, independent of the action policy?
#
# Setup: the SimulatedStudent from evaluation.py (hidden per-topic skill,
# prereq-gated learning, per-step forgetting). One study slot per simulated
# day. Every scheduler uses the SAME rule-based action mapping, so the only
# difference is WHICH topic gets the slot and WHEN:
#
#   random    — uniform random topic every day
#   rotation  — fixed round-robin (review interval = number of topics)
#   sm2       — SuperMemo-2 due dates from observed scores (stateful E-factor)
#   fsrs      — FSRS memory model; among due topics, lowest retrievability first
#
# Two regimes:
#   A "small course"  — 6 topics, homogeneous forgetting (0.01/day), ample
#                       review capacity (10 slots per topic).
#   B "large corpus"  — 24 topics, per-topic forgetting drawn from
#                       U[0.002, 0.06], scarce capacity (2.5 slots per topic).
#
# Honesty notes: the simulator's forgetting is LINEAR, while FSRS assumes
# power-law decay — FSRS gets no home-field advantage here. Regime A is
# where we EXPECT scheduling not to matter; the experiment is designed to
# find the boundary, not to flatter FSRS.
#
# Run:  python experiments/scheduler_comparison.py
# Haofei Sun

import random
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluation import SimulatedStudent, TOPICS
from spaced_repetition import calculate_next_review, score_to_rating

from fsrs import Scheduler, Card

N_DAYS = 60
N_SEEDS = 40
BASE_DATE = datetime(2026, 1, 1, tzinfo=timezone.utc)


class HeterogeneousStudent(SimulatedStudent):
    """Per-topic forgetting rates — some topics decay 30x faster than others."""

    def __init__(self, topics: list[str], rng: random.Random):
        super().__init__()
        self.forget_rates = {t: rng.uniform(0.002, 0.06) for t in topics}

    def study(self, topic: str, action: str) -> float:
        skill = self._skill(topic)
        observed = max(0.0, min(1.0, skill + random.gauss(0, self.noise)))

        action_mult = {"review": 1.6, "reinforce": 1.2, "advance": 0.5}[action]
        room_to_grow = 1.0 - skill
        gain = self.base_lr * action_mult * self._prereq_factor(topic) * room_to_grow
        self.skills[topic] = min(1.0, skill + gain)

        for t in list(self.skills.keys()):
            if t != topic:
                rate = self.forget_rates.get(t, self.forget_rate)
                self.skills[t] = max(0.0, self.skills[t] - rate)

        return observed


REGIMES = {
    "A · 6 topics, uniform decay": {
        "topics": TOPICS,
        "student": lambda topics, rng: SimulatedStudent(),
    },
    "B · 24 topics, per-topic decay": {
        "topics": [f"T{i:02d}" for i in range(1, 25)],
        "student": HeterogeneousStudent,
    },
}


def _rule_action(last_score: float | None) -> str:
    if last_score is None or last_score < 0.5:
        return "review"
    if last_score < 0.7:
        return "reinforce"
    return "advance"


# ---------- schedulers: pick which topic gets today's slot ----------

class RandomScheduler:
    name = "random"

    def __init__(self, topics, rng):
        self.topics, self.rng = topics, rng

    def pick(self, day):
        return self.rng.choice(self.topics)

    def record(self, topic, score, day):
        pass


class RotationScheduler:
    name = "rotation"

    def __init__(self, topics, rng):
        self.topics, self.i = topics, 0

    def pick(self, day):
        topic = self.topics[self.i % len(self.topics)]
        self.i += 1
        return topic

    def record(self, topic, score, day):
        pass


class SM2Scheduler:
    name = "sm2"

    def __init__(self, topics, rng):
        self.topics = topics
        self.state = {}   # topic -> (due_day, interval, easiness)

    def pick(self, day):
        unseen = [t for t in self.topics if t not in self.state]
        due = [(t, s) for t, s in self.state.items() if s[0] <= day]
        if due:
            # most overdue first
            return min(due, key=lambda x: x[1][0])[0]
        if unseen:
            return unseen[0]
        # nothing due — study whichever comes due soonest
        return min(self.state, key=lambda t: self.state[t][0])

    def record(self, topic, score, day):
        _, prev_interval, prev_ease = self.state.get(topic, (day, 1, 2.5))
        interval, ease = calculate_next_review(score, prev_interval, prev_ease)
        self.state[topic] = (day + interval, interval, ease)


class FSRSScheduler:
    name = "fsrs"

    def __init__(self, topics, rng):
        self.topics = topics
        self.scheduler = Scheduler()
        self.cards = {}   # topic -> Card

    def pick(self, day):
        now = BASE_DATE + timedelta(days=day)
        unseen = [t for t in self.topics if t not in self.cards]
        due = [t for t, c in self.cards.items() if c.due <= now]
        if due:
            # weakest memory first
            return min(due, key=lambda t: self.scheduler.get_card_retrievability(
                self.cards[t], now))
        if unseen:
            return unseen[0]
        return min(self.cards, key=lambda t: self.scheduler.get_card_retrievability(
            self.cards[t], now))

    def record(self, topic, score, day):
        now = BASE_DATE + timedelta(days=day)
        card = self.cards.get(topic, Card())
        card, _ = self.scheduler.review_card(card, score_to_rating(score), now)
        self.cards[topic] = card


SCHEDULERS = [RandomScheduler, RotationScheduler, SM2Scheduler, FSRSScheduler]


# ---------- simulation ----------

def run_once(scheduler_cls, regime: dict, seed: int) -> list[float]:
    """Returns mean skill across ALL topics after each day."""
    random.seed(seed)
    rng = random.Random(seed)
    topics = regime["topics"]
    student = regime["student"](topics, rng)
    sched = scheduler_cls(topics, rng)
    last_scores: dict[str, float] = {}
    curve = []
    for day in range(N_DAYS):
        topic = sched.pick(day)
        action = _rule_action(last_scores.get(topic))
        observed = student.study(topic, action)
        sched.record(topic, observed, day)
        last_scores[topic] = observed
        curve.append(statistics.mean(student._skill(t) for t in topics))
    return curve


def run_experiment() -> dict:
    results = {}
    for regime_name, regime in REGIMES.items():
        results[regime_name] = {}
        for cls in SCHEDULERS:
            curves = [run_once(cls, regime, seed=2000 + i) for i in range(N_SEEDS)]
            by_day = list(zip(*curves))
            results[regime_name][cls.name] = {
                "mean_curve": [statistics.mean(d) for d in by_day],
                "std_curve": [statistics.stdev(d) for d in by_day],
                "final_mean": statistics.mean(by_day[-1]),
                "final_std": statistics.stdev(by_day[-1]),
            }
    return results


# ---------- figure ----------

SERIES = {   # fixed categorical assignment (validated palette)
    "fsrs":     ("#2a78d6", "FSRS"),
    "sm2":      ("#eb6834", "SM-2"),
    "rotation": ("#1baf7a", "Rotation"),
    "random":   ("#eda100", "Random"),
}


def plot(results: dict, out_path: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), dpi=150, sharey=True)
    fig.patch.set_facecolor("#fcfcfb")

    for ax, (regime_name, regime_results) in zip(axes, results.items()):
        ax.set_facecolor("#fcfcfb")
        days = range(1, N_DAYS + 1)
        endpoints = []
        for key, (color, label) in SERIES.items():
            r = regime_results[key]
            mean, std = r["mean_curve"], r["std_curve"]
            ax.plot(days, mean, color=color, linewidth=2, label=label, zorder=3)
            ax.fill_between(days,
                            [m - s for m, s in zip(mean, std)],
                            [m + s for m, s in zip(mean, std)],
                            color=color, alpha=0.08, linewidth=0, zorder=2)
            endpoints.append((mean[-1], color))

        # end labels, nudged apart so ties don't overlap
        min_gap = 0.022
        placed = []
        for value, color in sorted(endpoints):
            y = value
            if placed and y - placed[-1] < min_gap:
                y = placed[-1] + min_gap
            placed.append(y)
            ax.annotate(f"{value:.2f}", xy=(N_DAYS, value), xytext=(N_DAYS + 1, y),
                        color=color, fontsize=9, fontweight="bold", va="center")
        ax.set_xlim(1, N_DAYS + 7)
        ax.set_title(regime_name, color="#0b0b0b", fontsize=11)
        ax.set_xlabel("Simulated day", color="#52514e")
        ax.grid(alpha=0.25, linewidth=0.5)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        for spine in ("left", "bottom"):
            ax.spines[spine].set_color("#c3c2b7")
        ax.tick_params(colors="#52514e")

    axes[0].set_ylabel("Mean hidden skill (all topics)", color="#52514e")
    axes[0].legend(loc="upper left", frameon=False, fontsize=9)
    fig.suptitle(f"When does smart review scheduling matter? "
                 f"{N_SEEDS} students, same action rule, band = ±1 SD",
                 color="#0b0b0b", fontsize=12, y=1.0)

    fig.tight_layout()
    fig.savefig(out_path, facecolor=fig.get_facecolor(), bbox_inches="tight")
    print(f"figure -> {out_path}")


if __name__ == "__main__":
    print(f"Scheduler comparison: {N_SEEDS} simulated students × {N_DAYS} days × 2 regimes")
    print("(same rule-based actions everywhere — only the schedule differs)\n")
    results = run_experiment()

    for regime_name, regime_results in results.items():
        print(f"Regime {regime_name}")
        header = f"  {'scheduler':<10} {'final mean skill':>18}"
        print(header)
        print("  " + "-" * (len(header) - 2))
        for name in ("fsrs", "sm2", "rotation", "random"):
            r = regime_results[name]
            print(f"  {name:<10} {r['final_mean']:>10.3f} ± {r['final_std']:.3f}")
        print()

    out = Path(__file__).parent.parent / "visuals" / "scheduler_comparison.png"
    plot(results, str(out))

# concept_graph.py
# Concept dependency graph - tracks which topics need other topics first
# Used by the planner to put prerequisites before advanced topics
# Haofei Sun - CSE 5360

from collections import defaultdict, deque

# default ML/AI prerequisite map
# format: {topic: [list of prerequisites]}
DEFAULT_PREREQS = {
    "Linear Algebra": [],
    "Probability": [],
    "Calculus": [],
    "Supervised Learning": ["Linear Algebra", "Probability"],
    "Unsupervised Learning": ["Linear Algebra", "Probability"],
    "Classification and Regression": ["Supervised Learning"],
    "Clustering": ["Unsupervised Learning"],
    "Dimensionality Reduction": ["Linear Algebra", "Unsupervised Learning"],
    "Neural Networks": ["Linear Algebra", "Calculus", "Supervised Learning"],
    "Backpropagation": ["Neural Networks", "Calculus"],
    "Deep Learning": ["Neural Networks", "Backpropagation"],
    "Convolutional Networks": ["Deep Learning"],
    "Recurrent Networks": ["Deep Learning"],
    "Transformers": ["Deep Learning", "Recurrent Networks"],
    "Reinforcement Learning": ["Probability", "Supervised Learning"],
    "Overfitting & Regularization": ["Supervised Learning"],
    "Evaluation Metrics": ["Classification and Regression"],
}


class ConceptGraph:
    """Simple DAG for topic prerequisites."""

    def __init__(self, prereqs: dict = None):
        self.prereqs = dict(prereqs or DEFAULT_PREREQS)

    def add_topic(self, topic: str, prereqs: list[str] = None):
        if topic not in self.prereqs:
            self.prereqs[topic] = list(prereqs or [])

    def get_prereqs(self, topic: str) -> list[str]:
        return self.prereqs.get(topic, [])

    def topological_sort(self, topics: list[str]) -> list[str]:
        """
        Sort topics so prereqs come first (Kahn's algorithm).
        Topics not in graph keep their original order at the end.
        """
        # only consider edges among the given topics
        topic_set = set(topics)
        in_degree = {t: 0 for t in topics}
        edges = defaultdict(list)

        for t in topics:
            for p in self.get_prereqs(t):
                if p in topic_set:
                    edges[p].append(t)
                    in_degree[t] += 1

        queue = deque([t for t in topics if in_degree[t] == 0])
        order = []
        while queue:
            t = queue.popleft()
            order.append(t)
            for nxt in edges[t]:
                in_degree[nxt] -= 1
                if in_degree[nxt] == 0:
                    queue.append(nxt)

        # add any remaining (in case of cycles, shouldn't happen normally)
        for t in topics:
            if t not in order:
                order.append(t)
        return order

    def missing_prereqs(self, topic: str, mastered: list[str]) -> list[str]:
        """Return prereqs that the student hasn't mastered yet."""
        return [p for p in self.get_prereqs(topic) if p not in mastered]

    def to_edges(self) -> list[tuple]:
        """Return (prereq, topic) edges for visualization."""
        edges = []
        for topic, ps in self.prereqs.items():
            for p in ps:
                edges.append((p, topic))
        return edges

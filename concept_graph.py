# concept_graph.py
# Concept dependency graph - tracks which topics need other topics first
# Supports multiple courses with cross-course prerequisite linking
# Used by the planner to put prerequisites before advanced topics
# Haofei Sun - CSE 5360

import json
from collections import defaultdict, deque
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
GRAPH_FILE = DATA_DIR / "concept_graph.json"

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

# cross-course prerequisite maps (course_name -> prereqs dict)
COURSE_PREREQS = {
    "AI Foundations (CSE 5360)": DEFAULT_PREREQS,
    "Data Science": {
        "Data Cleaning": [],
        "Exploratory Data Analysis": ["Data Cleaning"],
        "Statistical Testing": ["Probability"],
        "Feature Engineering": ["Exploratory Data Analysis"],
        "Model Selection": ["Supervised Learning", "Feature Engineering"],
        "Pipeline Design": ["Model Selection", "Data Cleaning"],
    },
    "Natural Language Processing": {
        "Tokenization": [],
        "Word Embeddings": ["Tokenization", "Linear Algebra"],
        "Language Models": ["Probability", "Word Embeddings"],
        "Sequence Models": ["Neural Networks", "Language Models"],
        "Attention Mechanism": ["Sequence Models"],
        "Transformers (NLP)": ["Attention Mechanism"],
        "Fine-tuning LLMs": ["Transformers (NLP)", "Deep Learning"],
    },
    "Computer Vision": {
        "Image Representation": ["Linear Algebra"],
        "Convolution Operations": ["Image Representation", "Calculus"],
        "CNN Architectures": ["Convolutional Networks", "Convolution Operations"],
        "Object Detection": ["CNN Architectures"],
        "Image Segmentation": ["CNN Architectures"],
        "Generative Models (Vision)": ["Deep Learning", "CNN Architectures"],
    },
}


class ConceptGraph:
    """DAG for topic prerequisites with cross-course linking and persistence."""

    def __init__(self, prereqs: dict = None, courses: list[str] = None):
        # start from defaults
        self.prereqs = dict(prereqs or DEFAULT_PREREQS)
        # optionally merge in cross-course prerequisites
        if courses:
            for course in courses:
                if course in COURSE_PREREQS:
                    self.prereqs.update(COURSE_PREREQS[course])
        # load any user-added edges from disk
        self._load_custom()

    def _load_custom(self):
        """Load user-defined edges from disk."""
        if GRAPH_FILE.exists():
            try:
                with open(GRAPH_FILE) as f:
                    custom = json.load(f)
                for topic, ps in custom.items():
                    if topic in self.prereqs:
                        for p in ps:
                            if p not in self.prereqs[topic]:
                                self.prereqs[topic].append(p)
                    else:
                        self.prereqs[topic] = ps
            except (json.JSONDecodeError, IOError):
                pass

    def _save_custom(self, custom: dict):
        with open(GRAPH_FILE, "w") as f:
            json.dump(custom, f, indent=2)

    def add_topic(self, topic: str, prereqs: list[str] = None):
        if topic not in self.prereqs:
            self.prereqs[topic] = list(prereqs or [])
        # persist the addition
        custom = {}
        if GRAPH_FILE.exists():
            try:
                with open(GRAPH_FILE) as f:
                    custom = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        custom[topic] = self.prereqs[topic]
        self._save_custom(custom)

    def add_edge(self, prereq: str, topic: str):
        """Add a single prerequisite edge and save."""
        if topic not in self.prereqs:
            self.prereqs[topic] = []
        if prereq not in self.prereqs[topic]:
            self.prereqs[topic].append(prereq)
        # also make sure prereq node exists
        if prereq not in self.prereqs:
            self.prereqs[prereq] = []
        self.add_topic(topic, self.prereqs[topic])

    def remove_edge(self, prereq: str, topic: str):
        """Remove a prerequisite edge."""
        if topic in self.prereqs and prereq in self.prereqs[topic]:
            self.prereqs[topic].remove(prereq)

    @staticmethod
    def available_courses() -> list[str]:
        return list(COURSE_PREREQS.keys())

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

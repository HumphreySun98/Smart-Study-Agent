# mock_claude.py
# Offline stand-in for the Anthropic client — returns canned phase responses.
# Haofei Sun - CSE 5360

import json
import time
import random


# --- canned phase responses ---

_OBSERVE_RESPONSE = {
    "topics": [
        "Supervised Learning",
        "Unsupervised Learning",
        "Neural Networks",
        "Overfitting & Regularization",
        "Evaluation Metrics",
    ],
    "descriptions": {
        "Supervised Learning": "Training a model on labeled input-output pairs to learn a mapping function.",
        "Unsupervised Learning": "Finding hidden patterns or structure in unlabeled data without predefined outputs.",
        "Neural Networks": "Layered architectures of interconnected neurons trained via backpropagation.",
        "Overfitting & Regularization": "Overfitting memorizes noise; L1/L2 and dropout prevent this.",
        "Evaluation Metrics": "Accuracy, precision, recall, F1-score, and MSE measure model quality.",
    },
    "summary": (
        "This lecture introduces core machine learning paradigms. "
        "Supervised learning covers classification and regression; unsupervised learning covers "
        "clustering and dimensionality reduction. Neural networks are presented as universal function "
        "approximators trained by backpropagation. Regularization techniques address overfitting, and "
        "a suite of evaluation metrics is discussed for model assessment."
    ),
}

_PLAN_RESPONSE = {
    "priorities": {
        "Supervised Learning": "medium",
        "Unsupervised Learning": "medium",
        "Neural Networks": "high",
        "Overfitting & Regularization": "high",
        "Evaluation Metrics": "low",
    },
    "sequence": [
        "Neural Networks",
        "Overfitting & Regularization",
        "Supervised Learning",
        "Unsupervised Learning",
        "Evaluation Metrics",
    ],
    "rationale": (
        "Neural Networks and Overfitting & Regularization are prioritised first because they form the "
        "conceptual backbone of modern ML. Supervised and Unsupervised Learning follow as context, and "
        "Evaluation Metrics are reviewed last since the student has shown prior familiarity with them."
    ),
}

# 3 MCQs per topic
_QUIZ_BANK = {
    "Neural Networks": [
        {
            "question": "Which algorithm is used to train a neural network by propagating errors backward through the layers?",
            "choices": ["A) Gradient Boosting", "B) Backpropagation", "C) K-Means", "D) Q-Learning"],
            "correct_answer": "B",
            "explanation": "Backpropagation computes gradients of the loss w.r.t. each weight using the chain rule.",
        },
        {
            "question": "What is the role of an activation function in a neural network?",
            "choices": ["A) Normalise input data", "B) Introduce non-linearity", "C) Reduce overfitting", "D) Compute the loss"],
            "correct_answer": "B",
            "explanation": "Without non-linear activations, stacking layers is equivalent to a single linear transformation.",
        },
        {
            "question": "Which term describes a neural network with more than one hidden layer?",
            "choices": ["A) Wide network", "B) Shallow network", "C) Deep neural network", "D) Sparse network"],
            "correct_answer": "C",
            "explanation": "Deep learning refers to networks with multiple hidden layers that learn hierarchical representations.",
        },
    ],
    "Overfitting & Regularization": [
        {
            "question": "A model achieves 99% training accuracy but only 60% test accuracy. This is most likely:",
            "choices": ["A) Underfitting", "B) Overfitting", "C) Correct generalisation", "D) Data leakage"],
            "correct_answer": "B",
            "explanation": "A large train-test accuracy gap is the classic sign of overfitting.",
        },
        {
            "question": "Which regularisation technique randomly zeros out neurons during training?",
            "choices": ["A) L1 regularisation", "B) L2 regularisation", "C) Dropout", "D) Batch normalisation"],
            "correct_answer": "C",
            "explanation": "Dropout randomly disables neurons each forward pass, reducing co-adaptation.",
        },
        {
            "question": "L2 regularisation adds which term to the loss function?",
            "choices": ["A) Sum of absolute weights", "B) Sum of squared weights", "C) Number of neurons", "D) Learning rate"],
            "correct_answer": "B",
            "explanation": "L2 (Ridge) penalises large weights by adding lambda * sum(w^2) to the loss.",
        },
    ],
    "Supervised Learning": [
        {
            "question": "Which of the following is a supervised learning task?",
            "choices": ["A) Clustering customer segments", "B) Predicting house prices", "C) Reducing data dimensions", "D) Generating new images"],
            "correct_answer": "B",
            "explanation": "Predicting house prices requires labeled (price) training data — it is a regression task.",
        },
        {
            "question": "In a classification problem, the model output is:",
            "choices": ["A) A continuous value", "B) A cluster assignment", "C) A discrete class label", "D) A probability distribution only"],
            "correct_answer": "C",
            "explanation": "Classification predicts a discrete category; regression predicts a continuous value.",
        },
        {
            "question": "Which algorithm builds a tree by splitting features to minimise impurity?",
            "choices": ["A) K-Nearest Neighbours", "B) Linear Regression", "C) Decision Tree", "D) PCA"],
            "correct_answer": "C",
            "explanation": "Decision trees split nodes using impurity measures like Gini index or entropy.",
        },
    ],
}

_FEEDBACK_TEMPLATES = {
    "high": (
        "Excellent work! You demonstrated a strong understanding of {topic}. "
        "Keep this momentum and move on to the next topic with confidence."
    ),
    "medium": (
        "Good effort on {topic}! You got most concepts right. "
        "Review the missed points briefly before advancing."
    ),
    "low": (
        "This topic needs more attention. Focus on the core concepts of {topic} "
        "and try the quiz again after reviewing your notes."
    ),
}

_ADAPT_RESPONSES = {
    "advance": {
        "action": "advance",
        "next_topic": "Overfitting & Regularization",
        "recommendation": "Great score! You're ready to move on to Overfitting & Regularization.",
    },
    "reinforce": {
        "action": "reinforce",
        "next_topic": None,
        "recommendation": "You're almost there. Do one more practice round on the same topic to solidify the concepts.",
    },
    "review": {
        "action": "review",
        "next_topic": None,
        "recommendation": "Re-read the lecture section on this topic, then retake the quiz.",
    },
}


# --- fake message shape to match the anthropic SDK ---

class _TextBlock:
    def __init__(self, text: str):
        self.type = "text"
        self.text = text


class _MockMessage:
    def __init__(self, text: str):
        self.content = [_TextBlock(text)]


# --- mock client ---

class MockAnthropic:
    """Drop-in for anthropic.Anthropic — picks a canned reply based on prompt keywords."""

    class _Messages:
        def create(self, model, max_tokens, messages, system="", thinking=None, **kwargs):
            time.sleep(0.6)   # tiny delay so the UI spinners don't flash

            prompt = messages[-1]["content"] if messages else ""

            if "key topics" in prompt or "Analyze the following" in prompt:
                return _MockMessage(json.dumps(_OBSERVE_RESPONSE))

            if "priorities" in prompt or "study plan" in prompt or "study planner" in prompt or "study planner" in system:
                return _MockMessage(json.dumps(_PLAN_RESPONSE))

            if "multiple-choice questions" in prompt or "Create exactly" in prompt:
                topic = _extract_topic(prompt)
                bank = _QUIZ_BANK.get(topic, _QUIZ_BANK["Neural Networks"])
                return _MockMessage(json.dumps(bank))

            if "scored" in prompt and "quiz" in prompt:
                score = _extract_score(prompt)
                level = "high" if score >= 0.7 else "medium" if score >= 0.5 else "low"
                topic = _extract_quiz_topic(prompt)
                return _MockMessage(_FEEDBACK_TEMPLATES[level].format(topic=topic))

            if "adaptive learning advisor" in system or "next action" in prompt:
                score = _extract_score(prompt)
                key = "advance" if score >= 0.7 else "reinforce" if score >= 0.5 else "review"
                return _MockMessage(json.dumps(_ADAPT_RESPONSES[key]))

            return _MockMessage("OK")

    def __init__(self, **kwargs):
        self.messages = self._Messages()


# --- prompt parsing helpers ---

def _extract_topic(prompt: str) -> str:
    for topic in _QUIZ_BANK:
        if topic in prompt:
            return topic
    return "Neural Networks"


def _extract_score(prompt: str) -> float:
    import re
    m = re.search(r"(\d+)%", prompt)
    if m:
        return int(m.group(1)) / 100
    m = re.search(r"scored\s+([\d.]+)", prompt)
    if m:
        return float(m.group(1))
    return 0.5


def _extract_quiz_topic(prompt: str) -> str:
    import re
    m = re.search(r"quiz about '([^']+)'", prompt)
    return m.group(1) if m else "this topic"

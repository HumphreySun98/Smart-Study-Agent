# smartstudy_agent.py
# Main agent code for SmartStudy - CSE 5360 midterm project
# Haofei Sun

import json
import os
from dataclasses import dataclass, field
from typing import Optional

import anthropic
from mock_claude import MockAnthropic

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _extract_json(text: str):
    """
    Robustly extract JSON from an LLM response. Handles:
      - plain JSON
      - ```json ... ``` fenced blocks
      - leading/trailing prose around a JSON object/array
      - mid-response truncation (auto-closes dangling brackets)
      - empty or whitespace-only responses (raises a clear error)
    """
    import re

    if not text or not text.strip():
        raise ValueError("LLM returned an empty response (possibly rate-limited or content-filtered).")

    s = text.strip()
    # strip markdown fences if present
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```\s*$", "", s)
    s = s.strip()

    # try the whole string as-is
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    # pick the intended outer delimiter based on which comes first in the text
    idx_brk = s.find("["); idx_brc = s.find("{")
    if idx_brk == -1: outer_open, outer_close = "{", "}"
    elif idx_brc == -1: outer_open, outer_close = "[", "]"
    elif idx_brk < idx_brc: outer_open, outer_close = "[", "]"
    else: outer_open, outer_close = "{", "}"

    # if the outer closer is missing entirely, the response is truncated — repair first
    if s.rfind(outer_close) == -1:
        repaired = _repair_truncated_json(s)
        if repaired is not None:
            return repaired

    # try delimiter match on intended outer type
    start = s.find(outer_open)
    if start != -1:
        end = s.rfind(outer_close)
        while end > start:
            try:
                return json.loads(s[start:end + 1])
            except json.JSONDecodeError:
                end = s.rfind(outer_close, start, end)

    # try the other delimiter type as a fallback
    alt_open, alt_close = ("{", "}") if outer_open == "[" else ("[", "]")
    start = s.find(alt_open)
    if start != -1:
        end = s.rfind(alt_close)
        while end > start:
            try:
                return json.loads(s[start:end + 1])
            except json.JSONDecodeError:
                end = s.rfind(alt_close, start, end)

    # final repair attempt
    repaired = _repair_truncated_json(s)
    if repaired is not None:
        return repaired

    raise ValueError(
        f"Could not parse JSON from LLM response. First 200 chars: {s[:200]!r}"
    )


def _repair_truncated_json(s: str):
    """
    Heuristic repair for truncated JSON: balance open braces/brackets,
    close any unterminated string, drop trailing incomplete elements.
    Returns parsed JSON or None if repair fails.
    """
    # find outer opener
    first = s.lstrip()[:1]
    if first not in ("{", "["):
        return None
    start = s.find(first)
    tail = s[start:]

    # strip any obvious trailing prose after last reasonable char
    stack = []
    in_str = False; esc = False
    last_valid = 0
    for i, ch in enumerate(tail):
        if esc:
            esc = False; continue
        if ch == "\\":
            esc = True; continue
        if ch == '"' and not esc:
            in_str = not in_str; continue
        if in_str:
            continue
        if ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if stack:
                stack.pop()
                if not stack:
                    last_valid = i + 1

    # attempt a few closing strategies
    candidates = []
    if in_str:
        closing = '"' + "".join("]" if c == "[" else "}" for c in reversed(stack))
    else:
        closing = "".join("]" if c == "[" else "}" for c in reversed(stack))

    # try (1) naive close
    candidates.append(tail + closing)
    # try (2) cut to last comma inside the outer structure, then close
    trimmed = tail
    comma = trimmed.rfind(",")
    if comma != -1:
        candidates.append(trimmed[:comma] + closing)
    # try (3) cut to last_valid and close
    if last_valid:
        candidates.append(tail[:last_valid])

    for cand in candidates:
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            continue
    return None


# ---- data classes to hold student info, plans, and quiz questions ----

@dataclass
class StudentProfile:
    """Keeps track of what the student knows and doesn't know."""
    topics_mastered: list[str] = field(default_factory=list)
    weak_areas: list[str] = field(default_factory=list)
    quiz_history: list[dict] = field(default_factory=list)

    def record_quiz(self, topic: str, score: float, missed: list[str]):
        self.quiz_history.append({"topic": topic, "score": score, "missed": missed})
        # 70% threshold from Bloom's mastery learning
        if score >= 0.7:
            if topic not in self.topics_mastered:
                self.topics_mastered.append(topic)
            if topic in self.weak_areas:
                self.weak_areas.remove(topic)
        else:
            if topic not in self.weak_areas:
                self.weak_areas.append(topic)

    def summary(self) -> str:
        return (
            f"Mastered: {self.topics_mastered or 'none yet'}\n"
            f"Weak areas: {self.weak_areas or 'none identified'}\n"
            f"Quizzes taken: {len(self.quiz_history)}"
        )


@dataclass
class StudyPlan:
    topics: list[str]
    priorities: dict[str, str]   # topic -> "high" / "medium" / "low"
    sequence: list[str]
    rationale: str


@dataclass
class QuizQuestion:
    topic: str
    question: str
    choices: list[str]        # ["A) ...", "B) ...", ...]
    correct_answer: str       # "A", "B", "C", or "D"
    explanation: str


# ---- the main agent class ----

class SmartStudyAgent:
    """
    5-phase adaptive learning agent:
    observe -> plan -> act -> evaluate -> adapt
    """

    def __init__(self, api_key: Optional[str] = None, mock: bool = False,
                 policy: Optional[str] = None):
        # backend selection: mock > anthropic > hf > mock fallback
        if mock:
            self.client = MockAnthropic()
            self.model = "mock"
        elif api_key or os.environ.get("ANTHROPIC_API_KEY"):
            self.client = anthropic.Anthropic(
                api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
            )
            self.model = "claude-opus-4-6"
        elif os.environ.get("HF_TOKEN"):
            # free HF Inference fallback (e.g. on Hugging Face Spaces)
            from hf_client import HFAnthropicAdapter
            self.client = HFAnthropicAdapter()
            self.model = "moonshotai/Kimi-K2-Instruct-0905"
        else:
            self.client = MockAnthropic()
            self.model = "mock"
        self.profile = StudentProfile()

        # Policy choice: "qlearning" (default) | "bandit" | "rule_based".
        # Bandit added in response to feedback: if state transitions are
        # small, contextual bandits are more sample-efficient than full RL.
        self.policy_name = (
            policy or os.environ.get("SMARTSTUDY_POLICY") or "qlearning"
        ).lower()
        self._topic_attempts: dict[str, int] = {}

    # --- Phase 1: OBSERVE ---
    # reads lecture content and pulls out the main topics

    def observe(self, content: str) -> dict:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            thinking={"type": "adaptive"},
            system=(
                "You are an expert educational content analyzer. "
                "Your job is to extract key topics from lecture materials "
                "and return structured JSON."
            ),
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Analyze the following lecture material and extract the key topics.\n\n"
                        "Return a JSON object with exactly these keys:\n"
                        '  "topics": [list of 4-8 key topic strings],\n'
                        '  "descriptions": {topic: one-sentence description},\n'
                        '  "summary": "one-paragraph overview of the material"\n\n'
                        "Lecture material:\n"
                        f"{content[:8000]}"
                    ),
                }
            ],
        )

        text = next(b.text for b in response.content if b.type == "text")
        return _extract_json(text)

    # --- Phase 2: PLAN ---
    # builds a study plan based on what the student already knows

    def plan(self, observed: dict) -> StudyPlan:
        profile_text = self.profile.summary()

        example = (
            '{\n'
            '  "priorities": {"Topic A": "high", "Topic B": "medium"},\n'
            '  "sequence": ["Topic A", "Topic B"],\n'
            '  "rationale": "Short explanation of the ordering."\n'
            '}'
        )
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            thinking={"type": "adaptive"},
            system=(
                "You are an intelligent study planner. "
                "Given a list of topics and a student's performance profile, "
                "create a prioritised, personalised study plan. "
                "Return ONLY a JSON object with EXACTLY three keys: "
                "priorities, sequence, rationale."
            ),
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Topics extracted from lecture:\n{json.dumps(observed['topics'], indent=2)}\n\n"
                        f"Topic descriptions:\n{json.dumps(observed['descriptions'], indent=2)}\n\n"
                        f"Student profile:\n{profile_text}\n\n"
                        "Return a JSON object with these keys:\n"
                        "  priorities — object mapping each topic to one of \"high\", \"medium\", or \"low\"\n"
                        "  sequence — array of topic names in the order they should be studied\n"
                        "  rationale — a short string explaining the plan\n\n"
                        "Example of the required format:\n"
                        f"{example}"
                    ),
                }
            ],
        )

        text = next(b.text for b in response.content if b.type == "text")
        data = _extract_json(text)

        return StudyPlan(
            topics=observed["topics"],
            priorities=data["priorities"],
            sequence=data["sequence"],
            rationale=data["rationale"],
        )

    # --- Phase 3: ACT ---
    # generates MCQ quiz questions for a specific topic

    def act(self, topic: str, topic_description: str, n: int = 3) -> list[QuizQuestion]:
        example = (
            '[\n'
            '  {\n'
            '    "question": "Short question text?",\n'
            '    "choices": ["A) option 1", "B) option 2", "C) option 3", "D) option 4"],\n'
            '    "correct_answer": "B",\n'
            '    "explanation": "Short explanation why B is correct."\n'
            '  }\n'
            ']'
        )
        response = self.client.messages.create(
            model=self.model,
            max_tokens=3500,
            system=(
                "You are an expert quiz writer for university-level AI courses. "
                "Create clear, CONCISE multiple-choice questions. "
                "Each question, choice, and explanation should be short. "
                "Return ONLY a JSON array, no prose before or after."
            ),
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Topic: {topic}\n"
                        f"Description: {topic_description}\n\n"
                        f"Create exactly {n} multiple-choice questions. "
                        "Keep each question under 30 words. Keep each choice under 15 words. "
                        "Keep each explanation under 30 words.\n\n"
                        "Return a JSON array. Each element has these keys:\n"
                        "  question — the question text (string)\n"
                        "  choices — array of exactly 4 strings, each prefixed \"A) \", \"B) \", \"C) \", \"D) \"\n"
                        "  correct_answer — single letter A, B, C, or D\n"
                        "  explanation — short string\n\n"
                        "Example of the required format:\n"
                        f"{example}"
                    ),
                }
            ],
        )

        text = next(b.text for b in response.content if b.type == "text")
        raw = _extract_json(text)

        return [
            QuizQuestion(
                topic=topic,
                question=q["question"],
                choices=q["choices"],
                correct_answer=q["correct_answer"].strip().upper()[0],
                explanation=q["explanation"],
            )
            for q in raw
        ]

    # --- Phase 4: EVALUATE ---
    # checks answers, calculates score, gets feedback from Claude

    def evaluate(
        self, questions: list[QuizQuestion], answers: list[str]
    ) -> dict:
        correct_indices = []
        incorrect_indices = []
        missed_concepts = []

        for i, (q, ans) in enumerate(zip(questions, answers)):
            if ans.strip().upper()[0] == q.correct_answer:
                correct_indices.append(i)
            else:
                incorrect_indices.append(i)
                missed_concepts.append(q.topic)

        score = len(correct_indices) / len(questions) if questions else 0.0

        # build a summary of what they got wrong so Claude can give good feedback
        wrong_details = "\n".join(
            f"Q{i+1}: {questions[i].question} — student said {answers[i]}, "
            f"correct is {questions[i].correct_answer}. {questions[i].explanation}"
            for i in incorrect_indices
        )

        feedback_response = self.client.messages.create(
            model=self.model,
            max_tokens=512,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"A student scored {score:.0%} on a quiz about "
                        f"'{questions[0].topic if questions else 'unknown'}'.\n\n"
                        + (f"Mistakes:\n{wrong_details}\n\n" if wrong_details else "All correct!\n\n")
                        + "Write 2-3 sentences of encouraging, constructive feedback."
                    ),
                }
            ],
        )

        feedback = next(b.text for b in feedback_response.content if b.type == "text")

        return {
            "score": score,
            "correct": correct_indices,
            "incorrect": incorrect_indices,
            "missed_concepts": list(set(missed_concepts)),
            "feedback": feedback,
        }

    # --- Phase 5: ADAPT ---
    # updates the student profile, uses RL policy for action, then gets LLM recommendation

    def adapt(self, topic: str, evaluation: dict) -> dict:
        # get the previous score for this topic (for RL update)
        prev_score = 0.0
        for h in reversed(self.profile.quiz_history):
            if h.get("topic") == topic:
                prev_score = h.get("score", 0.0)
                break

        self.profile.record_quiz(
            topic=topic,
            score=evaluation["score"],
            missed=evaluation["missed_concepts"],
        )

        # --- Policy decides the action ---
        new_score = evaluation["score"]
        self._topic_attempts[topic] = self._topic_attempts.get(topic, 0) + 1

        if self.policy_name == "bandit":
            from bandit_policy import LinUCBBandit
            policy = LinUCBBandit()
            attempts = self._topic_attempts[topic]
            rl_action = policy.choose_action(
                prev_score, attempts_on_topic=attempts, topic_idx=0,
            )
            reward = (new_score - prev_score) * 10.0
            policy.update(prev_score, rl_action, reward,
                          attempts_on_topic=attempts, topic_idx=0)
            policy_label = "contextual_bandit"
        elif self.policy_name == "rule_based":
            if new_score < 0.5:
                rl_action = "review"
            elif new_score < 0.7:
                rl_action = "reinforce"
            else:
                rl_action = "advance"
            policy_label = "rule_based"
        else:
            from rl_policy import QLearningPolicy
            policy = QLearningPolicy()
            rl_action = policy.choose_action(new_score)
            policy.update(prev_score, rl_action, new_score)
            policy_label = "qlearning"

        # --- LLM generates the recommendation text (but action comes from RL) ---
        response = self.client.messages.create(
            model=self.model,
            max_tokens=512,
            thinking={"type": "adaptive"},
            system=(
                "You are an adaptive learning advisor. "
                "The RL policy has already decided the action. "
                "Your job is to explain the decision to the student. "
                "Return only valid JSON."
            ),
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Quiz topic: {topic}\n"
                        f"Score: {evaluation['score']:.0%}\n"
                        f"Missed concepts: {evaluation['missed_concepts']}\n"
                        f"RL policy decision: {rl_action}\n"
                        f"Updated profile:\n{self.profile.summary()}\n\n"
                        f"The RL policy chose '{rl_action}'. Explain this to the student.\n"
                        "Return JSON with:\n"
                        f'  "action": "{rl_action}",\n'
                        '  "next_topic": "suggested next topic or null",\n'
                        '  "recommendation": "brief explanation of why this action makes sense"\n'
                    ),
                }
            ],
        )

        text = next(b.text for b in response.content if b.type == "text")
        try:
            result = _extract_json(text)
        except ValueError:
            # Adapt phase is non-critical — if LLM output is bad, fall back to a default
            result = {
                "action": rl_action,
                "next_topic": None,
                "recommendation": f"Policy chose '{rl_action}' based on score {evaluation['score']:.0%}.",
            }
        # ensure the policy's action is used (not overridden by LLM)
        result["action"] = rl_action
        result["policy"] = policy_label
        result["rl_policy_used"] = True
        return result

    # --- helper: run all phases in sequence ---

    def run_session(self, content: str, on_event=None):
        """Run the full OPEAA loop on some lecture content."""
        def emit(phase, data):
            if on_event:
                on_event(phase, data)
            return data

        observed = emit("observe", self.observe(content))
        plan = emit("plan", self.plan(observed))

        return {
            "observed": observed,
            "plan": plan,
            "profile": self.profile,
        }

# SmartStudy Agent — Technical Design Document

**CSE 5360 Artificial Intelligence I**
University of Texas at Arlington
Author: Haofei Sun

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [AI Model — Claude (LLM)](#2-ai-model--claude-llm)
3. [System Architecture](#3-system-architecture)
4. [Agent Design & Decision Making](#4-agent-design--decision-making)
5. [Phase-by-Phase Technical Breakdown](#5-phase-by-phase-technical-breakdown)
6. [Knowledge Representation](#6-knowledge-representation)
7. [Adaptive Learning Policy](#7-adaptive-learning-policy)
8. [Prompt Engineering Strategy](#8-prompt-engineering-strategy)
9. [Data Flow Diagram](#9-data-flow-diagram)
10. [Design Decisions & Trade-offs](#10-design-decisions--trade-offs)
11. [Limitations & Future Work](#11-limitations--future-work)

---

## 1. System Overview

SmartStudy Agent is an **AI-driven tutoring agent** that implements a closed-loop adaptive learning cycle. It is categorized as a **goal-based agent** in the classical AI sense: the agent has an explicit goal (maximize student mastery of lecture material), perceives the environment (lecture content + student quiz performance), and selects actions (generate quiz, recommend review, advance topic) to achieve that goal.

The loop is inspired by the **OODA Loop** (Observe–Orient–Decide–Act) used in autonomous systems, adapted to an educational context:

```
Observe  →  perceive lecture content
Plan     →  orient: build a knowledge map and prioritize gaps
Act      →  decide: generate targeted quiz questions
Evaluate →  measure student response
Adapt    →  update internal model and select next action
```

This is fundamentally different from a Q&A chatbot. A chatbot is **reactive** (responds to queries). SmartStudy Agent is **proactive**: it autonomously decides what to teach next based on a maintained student model.

---

## 2. AI Model — Claude (LLM)

### 2.1 Model Selection

The system uses **Claude claude-opus-4-6** by Anthropic as its core reasoning engine.

| Property | Value |
|----------|-------|
| Model ID | `claude-opus-4-6` |
| Provider | Anthropic |
| Context window | 200,000 tokens |
| Max output tokens | 128,000 tokens |
| API type | REST / Anthropic Python SDK |
| Reasoning | Adaptive thinking (`thinking: {type: "adaptive"}`) |

**Why Claude over other LLMs?**

- **Instruction following**: Claude reliably returns structured JSON when asked — critical for parsing phase outputs programmatically.
- **Adaptive thinking**: Claude claude-opus-4-6 supports an internal chain-of-thought reasoning mode (`thinking: adaptive`) that improves accuracy on multi-step decisions (planning, adaptation) without requiring the developer to manually craft chain-of-thought prompts.
- **Long context**: Lecture materials (PDFs) can be thousands of tokens. Claude's 200K context window handles full lecture documents without chunking.

### 2.2 What Is a Large Language Model?

A Large Language Model is a neural network trained on massive text corpora using a **Transformer architecture**. It learns to predict the next token given a context, developing emergent abilities including reasoning, summarization, and structured generation.

Key components relevant to this project:

- **Tokenization**: Input text is split into sub-word tokens. Claude processes the prompt token-by-token.
- **Attention mechanism**: Self-attention allows the model to relate distant parts of the input (e.g., connecting a topic name in the lecture to its description later in the text).
- **In-context learning**: The model adapts its output based on examples and instructions in the prompt without any weight updates — this is how we guide it to return JSON.

### 2.3 Adaptive Thinking (Extended Reasoning)

For complex phases (OBSERVE, PLAN, ADAPT), the system sets:
```python
thinking={"type": "adaptive"}
```

This instructs Claude to perform **internal chain-of-thought reasoning** before generating the final answer. The model produces hidden reasoning tokens that are not returned to the user but improve output quality — similar to how a human "thinks before speaking." This is especially important in the PLAN phase, where the model must weigh multiple topics against the student's history to produce a sensible priority ordering.

---

## 3. System Architecture

### 3.1 Component Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                      SmartStudy Agent                        │
│                                                              │
│  ┌─────────────┐     ┌──────────────────────────────────┐   │
│  │   Input     │     │         SmartStudyAgent           │   │
│  │  Layer      │────▶│  observe() plan() act()           │   │
│  │             │     │  evaluate() adapt()               │   │
│  │ PDF/Text    │     └──────────────┬───────────────────┘   │
│  └─────────────┘                   │                         │
│                                    │ API calls               │
│  ┌─────────────┐                   ▼                         │
│  │  Student    │     ┌──────────────────────────────────┐   │
│  │  Profile    │◀───▶│      Claude API (LLM)            │   │
│  │             │     │    claude-opus-4-6               │   │
│  │ - mastered  │     │  + adaptive thinking             │   │
│  │ - weak      │     └──────────────────────────────────┘   │
│  │ - history   │                                             │
│  └─────────────┘     ┌──────────────────────────────────┐   │
│                      │      Output Layer                 │   │
│                      │  StudyPlan / QuizQuestion /       │   │
│                      │  Evaluation / Recommendation      │   │
│                      └──────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 Layer Descriptions

**Input Layer** — `pypdf` extracts raw text from uploaded lecture PDFs. Text is passed as a string to the agent (capped at 8,000 tokens per call to stay within practical limits).

**SmartStudyAgent** — The central controller. Orchestrates the 5-phase loop, maintains the `StudentProfile`, and calls Claude for each reasoning step.

**Claude API** — Stateless reasoning engine. Each call is independent; the agent reconstructs context in each prompt from the `StudentProfile` and previous phase outputs.

**StudentProfile** — The agent's **world model** of the student. Stores which topics are mastered (score ≥ 70%) and which are weak areas. This is the only persistent state between phases.

**Output Layer** — Typed Python dataclasses (`StudyPlan`, `QuizQuestion`) and dicts for evaluation/adaptation results.

---

## 4. Agent Design & Decision Making

### 4.1 Agent Classification

SmartStudy Agent falls under **goal-based agents** with elements of **utility-based** reasoning:

| Property | Value |
|----------|-------|
| Agent type | Goal-based + utility-based |
| Environment | Partially observable (only quiz answers are observed, not full student knowledge) |
| Environment type | Sequential (each action depends on previous state) |
| Actuators | Recommendations, quiz questions, study plans |
| Sensors | Lecture text, student quiz answers |

### 4.2 Decision Making in ADAPT

The ADAPT phase is where the agent makes its core **policy decision**. Given:
- Current quiz score
- Topics in weak areas
- Full quiz history

The agent selects one of three actions:

```
score ≥ 70%  →  ADVANCE   (move to next topic in plan)
50% ≤ score < 70%  →  REINFORCE  (retry same topic)
score < 50%  →  REVIEW    (re-read lecture, retry later)
```

This is a **heuristic policy** (rule-based thresholds), not a learned policy. It is simple but interpretable — important for an educational tool where the rationale should be explainable to the student.

Claude adds a layer of **natural language reasoning** on top of the rule: it generates a textual explanation of *why* the action was chosen, making the system's decisions transparent.

### 4.3 PEAS Description

| Element | Description |
|---------|-------------|
| **Performance** | Fraction of topics mastered; quiz score improvement over sessions |
| **Environment** | Lecture PDF; student answers; session history |
| **Actuators** | Study plan output; quiz questions; feedback text; next-action recommendation |
| **Sensors** | Text content of lecture; student's multiple-choice answers |

---

## 5. Phase-by-Phase Technical Breakdown

### 5.1 OBSERVE — Knowledge Extraction

**Goal:** Convert unstructured lecture text → structured topic representation.

**Method:** Zero-shot structured extraction prompt. The prompt explicitly specifies the output schema (JSON with keys `topics`, `descriptions`, `summary`). Claude uses its pre-trained language understanding to:
1. Identify semantically distinct concepts in the text
2. Name each topic concisely
3. Write a one-sentence definition for each

**Why not use classical NLP (NER, TF-IDF)?**

Traditional NLP methods for topic extraction (LDA, TF-IDF, NER) require either:
- A pre-trained domain-specific model, or
- A large corpus to compute term frequencies

Claude's in-context learning achieves equivalent or better extraction with a single API call and no training data.

**Technical detail — JSON parsing robustness:**
```python
clean = text.strip()
    .removeprefix("```json")
    .removeprefix("```")
    .removesuffix("```")
    .strip()
return json.loads(clean)
```
Claude sometimes wraps JSON in markdown code fences. The parser strips these before passing to `json.loads`.

---

### 5.2 PLAN — Heuristic Study Planning

**Goal:** Given extracted topics and student history, produce an ordered study sequence with priorities.

**Inputs to Claude:**
- List of topics + descriptions (from OBSERVE)
- `StudentProfile.summary()` — mastered topics, weak areas, quiz count

**Output schema:**
```json
{
  "priorities": {"Topic A": "high", "Topic B": "low"},
  "sequence": ["Topic A", "Topic B", ...],
  "rationale": "explanation"
}
```

**Planning heuristic (enforced via prompt):**
- Topics in `weak_areas` → `"high"` priority, placed early in sequence
- Topics in `topics_mastered` → `"low"` priority, placed at end for review
- New topics → `"medium"` priority

This is analogous to a **greedy heuristic search**: the agent prioritizes states (topics) with the highest expected utility gain (learning from a weak area improves overall mastery more than re-studying a mastered topic).

---

### 5.3 ACT — Quiz Generation

**Goal:** Generate `n` multiple-choice questions for a specific topic.

**Why multiple-choice?** MCQ format allows automated scoring (string comparison) without requiring natural language answer evaluation, which would add significant complexity and cost.

**Prompt structure:** The prompt specifies the exact JSON array schema for questions. Each question must include:
- Question text
- 4 choices (A–D format)
- Correct answer key
- Explanation of why the answer is correct

The explanation is critical — it enables the EVALUATE phase to provide specific, actionable feedback rather than just "incorrect."

---

### 5.4 EVALUATE — Performance Analysis

**Goal:** Score answers, identify missed concepts, generate personalized feedback.

**Scoring algorithm** (deterministic, no LLM required):
```python
score = len(correct_indices) / len(questions)
```

**Missed concept extraction:** Any topic where the student answered incorrectly is added to `missed_concepts`. This list is passed to both ADAPT (to update the profile) and Claude (to generate targeted feedback).

**Feedback generation:** Claude receives:
- Score percentage
- Details of each wrong answer (question, student's answer, correct answer, explanation)

And returns 2–3 sentences of encouraging, constructive feedback. This is the only LLM call in EVALUATE — the scoring itself is deterministic.

---

### 5.5 ADAPT — Profile Update & Recommendation

**Goal:** Update the student model and decide the next action.

**Profile update (deterministic rule):**
```python
if score >= 0.7:
    topics_mastered.append(topic)
    weak_areas.remove(topic)   # graduate from weak areas
else:
    weak_areas.append(topic)
```

**Action selection (LLM-assisted):** Claude receives the updated profile and score, then selects `review | reinforce | advance` with a textual rationale. The LLM adds nuance: for example, if a student scored 68% but the topic is already in `weak_areas` from a previous session, Claude may recommend `review` rather than `reinforce`.

---

## 6. Knowledge Representation

The agent maintains two forms of knowledge:

### 6.1 Declarative Knowledge — Topic Descriptions

Stored as a Python `dict`:
```python
{
  "Neural Networks": "Layered architectures of interconnected neurons...",
  "Overfitting": "When a model memorizes training noise..."
}
```
This is a lightweight **semantic network** — topics as nodes, descriptions as node attributes. Relationships between topics are implicitly encoded in Claude's weights rather than explicitly stored.

### 6.2 Procedural Knowledge — StudentProfile

```python
@dataclass
class StudentProfile:
    topics_mastered: list[str]   # topics scored ≥ 70%
    weak_areas: list[str]        # topics scored < 70%
    quiz_history: list[dict]     # full record of all quizzes
```

This is a **belief state** in the POMDP sense — the agent's best estimate of the student's knowledge given the observed quiz answers. It is updated after every ADAPT phase.

**Limitation:** The profile only tracks topic-level mastery. It cannot represent finer-grained concept-level gaps (e.g., a student may understand backpropagation but not activation functions, both under "Neural Networks"). Future work would use a concept graph with more granular nodes.

---

## 7. Adaptive Learning Policy

The policy governing the agent's behavior can be stated as:

```
π(state) → action

where:
  state  = (current_topic, score, StudentProfile)
  action ∈ {review, reinforce, advance}
```

**Threshold-based policy (current implementation):**

| Condition | Action | Rationale |
|-----------|--------|-----------|
| score ≥ 0.70 | `advance` | Mastery threshold met; proceed |
| 0.50 ≤ score < 0.70 | `reinforce` | Partial understanding; practice more |
| score < 0.50 | `review` | Insufficient understanding; re-read material |

The 70% threshold is a commonly used mastery criterion in educational psychology (Bloom's Mastery Learning model).

**Why not use Reinforcement Learning?**

A learned RL policy would require:
1. A reward signal (e.g., long-term retention test scores)
2. Many episodes of student interaction to train on
3. A simulator or real students to generate training data

For this project scope, a heuristic policy is appropriate. It is interpretable, requires no training data, and produces reasonable behavior. RL is noted as a **future improvement**.

---

## 8. Prompt Engineering Strategy

All LLM calls follow a consistent pattern:

### 8.1 System Prompt — Role Assignment

```python
system="You are an expert educational content analyzer. ..."
```

Assigns Claude a specific expert role. This constrains the output distribution toward domain-appropriate language and improves JSON reliability.

### 8.2 User Prompt — Schema Specification

Every prompt that expects JSON explicitly states the output schema:

```
Return a JSON object with exactly these keys:
  "topics": [list of 4-8 key topic strings],
  "descriptions": {topic: one-sentence description},
  "summary": "one-paragraph overview"
```

This is **zero-shot structured generation** — no examples are provided; the schema specification alone is sufficient.

### 8.3 Context Injection

For PLAN and ADAPT, the prompt includes the student's current profile:

```python
f"Student profile:\n{self.profile.summary()}"
```

This gives Claude the necessary context to make personalized decisions without maintaining server-side session state — all context is reconstructed per-call.

### 8.4 Why Not Use Function Calling / Tool Use?

The Anthropic API supports structured tool use (function calling). We chose plain JSON prompting instead because:
- It requires less boilerplate for simple schemas
- Output is identical to tool use for our use case
- Easier to understand and explain in an academic context

---

## 9. Data Flow Diagram

```
PDF / Text Input
      │
      ▼
  [OBSERVE]
  Claude extracts:
  - topics: list[str]
  - descriptions: dict
  - summary: str
      │
      ▼
  [PLAN]
  Claude receives topics + StudentProfile
  Outputs:
  - priorities: dict[str, "high"|"medium"|"low"]
  - sequence: list[str]        ← ordered study path
  - rationale: str
      │
      ▼  (for each topic in sequence)
  [ACT]
  Claude generates n QuizQuestions
  - question: str
  - choices: list[str]
  - correct_answer: "A"|"B"|"C"|"D"
  - explanation: str
      │
      │  student answers: list["A"|"B"|"C"|"D"]
      ▼
  [EVALUATE]
  Deterministic scoring:
  - score: float  (0.0 – 1.0)
  - correct / incorrect indices
  - missed_concepts: list[str]
  Claude generates:
  - feedback: str
      │
      ▼
  [ADAPT]
  Deterministic profile update:
  - StudentProfile.record_quiz(topic, score, missed)
  Claude decides:
  - action: "review"|"reinforce"|"advance"
  - next_topic: str | None
  - recommendation: str
      │
      └─── loop back to [ACT] with next_topic
           or terminate session
```

---

## 10. Design Decisions & Trade-offs

### 10.1 Stateless LLM Calls vs. Conversational History

**Decision:** Each Claude call is stateless — no conversation history is maintained across phases.

**Trade-off:**
- Pro: Simpler code, no token accumulation, no context window overflow
- Con: Claude cannot refer back to earlier phases; all context must be re-injected per call

**Why this is acceptable:** Each phase has well-defined inputs and outputs. The `StudentProfile` captures all persistent state needed for personalization.

---

### 10.2 Heuristic Policy vs. Learned Policy

**Decision:** Use threshold-based heuristics for adapt() rather than a trained RL policy.

**Trade-off:**
- Pro: No training data required, fully interpretable, deterministic
- Con: Cannot discover optimal thresholds from data; does not improve over time

---

### 10.3 Multiple-Choice vs. Open-Ended Quiz

**Decision:** Use MCQ format.

**Trade-off:**
- Pro: Automated scoring (O(1) string comparison), no NLU required for grading
- Con: MCQ tests recognition, not recall; students can guess (25% baseline)

**Mitigation:** 3–5 questions per topic reduces guessing variance. Future work: add short-answer questions with LLM-based grading.

---

### 10.4 Single-Model Architecture vs. Multi-Agent

**Decision:** One `SmartStudyAgent` instance handles all phases via sequential LLM calls.

**Trade-off:**
- Pro: Simple, low latency, easy to debug
- Con: All reasoning bottlenecks through one model; cannot parallelize phases

**Alternative considered:** A multi-agent architecture where separate specialized agents handle OBSERVE, PLAN, ACT etc. Rejected for this scope due to added complexity.

---

## 11. Limitations & Future Work

### Current Limitations

| Limitation | Impact |
|-----------|--------|
| `StudentProfile` is in-memory only | Data lost when program exits; no cross-session persistence |
| MCQ only | Does not test free-recall or application skills |
| Heuristic adapt policy | Fixed thresholds may not suit all learners |
| No concept-level granularity | Cannot distinguish sub-concepts within a topic |
| Single language (English) | Lecture materials must be in English |
| PDF extraction quality | Tables, equations, and diagrams are lost during text extraction |

### Planned Improvements (Final Project)

1. **Persistent storage** — Save `StudentProfile` to JSON/SQLite so it survives across sessions
2. **Concept graph** — Replace flat topic list with a directed graph (prerequisite relationships)
3. **Reinforcement Learning policy** — Train a policy on simulated student interactions to discover optimal thresholds
4. **Open-ended questions** — Use Claude to grade free-text answers for higher-order assessment
5. **Multi-modal input** — Use Claude's vision capability to process lecture slides with diagrams
6. **Web interface** — Replace terminal demo with a browser-based UI

---

## References

- Russell, S., & Norvig, P. (2020). *Artificial Intelligence: A Modern Approach* (4th ed.) — Agent design, PEAS, goal-based agents
- Bloom, B. S. (1968). Learning for mastery — 70% mastery threshold criterion
- Vaswani et al. (2017). Attention Is All You Need — Transformer architecture underlying Claude
- Anthropic (2024). Claude claude-opus-4-6 Model Card — Model capabilities and API documentation
- VanLehn, K. (2011). The relative effectiveness of human tutoring, intelligent tutoring systems, and other tutoring systems — Theoretical basis for adaptive tutoring

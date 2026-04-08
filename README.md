# SmartStudy Agent

> An adaptive AI study agent powered by Claude — observes lecture content, plans personalized study paths, generates quizzes, evaluates answers, and adapts in real time.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Claude API](https://img.shields.io/badge/Claude-opus--4--6-purple.svg)](https://www.anthropic.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-red.svg)](https://streamlit.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

SmartStudy Agent is a goal-based, partially observable AI agent that turns any lecture material into a fully personalized learning experience. Unlike a chatbot, it maintains a persistent belief state about student knowledge and uses an adaptive policy to decide what to study next.

---

## Why SmartStudy?

Traditional study tools are static. They show you the same content regardless of what you already know. SmartStudy Agent solves this by closing the loop:

| Problem | SmartStudy's Solution |
|---------|----------------------|
| Generic study materials | Topics extracted and prioritized per student |
| No feedback on weak areas | Quiz answers update a persistent belief state |
| Same recommendations for everyone | Q-learning policy adapts per student trajectory |
| Forgetting without practice | SM-2 spaced repetition scheduler |
| Out-of-order topics | Topological sort over a concept dependency graph |

---

## Architecture

SmartStudy implements the **OPEAA loop** — a five-phase adaptive agent cycle:

```
       ┌─────────────────────────────────────────────────┐
       │              Lecture Materials                  │
       │   PDF · TXT · MD · DOCX · PPTX · VTT · SRT      │
       └────────────────────┬────────────────────────────┘
                            ▼
       ┌─────────────────────────────────────────────────┐
       │     Claude API  ·  claude-opus-4-6              │
       │     thinking: { type: "adaptive" }              │
       └────────────────────┬────────────────────────────┘
                            ▼
       ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
       │ OBSERVE │─▶│  PLAN   │─▶│   ACT   │─▶│ EVALUATE│
       │         │  │  + DAG  │  │  quizzes│  │  + LLM  │
       │ extract │  │   sort  │  │  3 MCQs │  │feedback │
       │ topics  │  │         │  │         │  │         │
       └─────────┘  └─────────┘  └─────────┘  └────┬────┘
            ▲                                       │
            │           ┌──────────────────────────▼┐
            │           │           ADAPT           │
            └───────────┤  Heuristic OR Q-learning  │
                        │  StudentProfile updated   │
                        └─────────┬─────────────────┘
                                  ▼
                  ┌─────────────────────────────────┐
                  │   Persistent Belief State       │
                  │   (JSON storage · per student)  │
                  └─────────────────────────────────┘
                                  │
                ┌─────────────────┼─────────────────┐
                ▼                 ▼                 ▼
          Spaced Repetition  Concept Graph    Streamlit UI
            (SM-2)            (DAG topo sort)   (8 pages)
```

The agent is modeled as a **POMDP** (partially observable Markov decision process):
- **State** — student's true knowledge (hidden)
- **Belief state** — `StudentProfile` (mastered topics, weak areas, quiz history)
- **Actions** — `advance` · `reinforce` · `review`
- **Observations** — student answers to generated quizzes
- **Reward** — improvement in quiz scores over time

---

## Features

### Core Agent
- **5-phase OPEAA loop** — Observe → Plan → Act → Evaluate → Adapt
- **Claude integration** with `thinking: {type: "adaptive"}` for internal reasoning
- **Goal-based agent design** following Russell & Norvig's PEAS framework
- **POMDP belief state** persisted across sessions
- **Two adaptive policies** — heuristic (Bloom's 70% mastery threshold) and tabular Q-learning

### Knowledge & Memory
- **Concept dependency graph** — Kahn's algorithm topological sort over a topic prerequisite DAG
- **SM-2 spaced repetition** — schedules reviews based on forgetting curves
- **Persistent JSON storage** — student profiles survive across sessions
- **Multi-student support** with peer comparison dashboard

### Input & Evaluation
- **7 input formats** — PDF, TXT, MD, DOCX, PPTX, VTT, SRT
- **Quantitative evaluation** — Monte Carlo simulation of adaptive vs random baselines
- **Mock client** — `MockAnthropic` lets you run the entire system offline without an API key

### User Interface
- **Streamlit web app** with 8 pages
- **Interactive terminal UI** powered by `rich`
- **Auto-demo mode** for video recording

---

## Installation

```bash
git clone https://github.com/<your-username>/smartstudy-agent.git
cd smartstudy-agent
pip install -r requirements.txt
```

Set your Claude API key:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Get a key from [console.anthropic.com](https://console.anthropic.com). New accounts receive $5 in free credit.

---

## Quick Start

### Web App
```bash
streamlit run app.py
```
Open **http://localhost:8501**, create a student in the sidebar, then go to **📖 Study Session** to run the full OPEAA loop on a sample ML lecture or your own PDF.

### Terminal demo (interactive)
```bash
python demo.py
python demo.py --pdf path/to/lecture.pdf
python demo.py --mock                  # offline mode, no API key needed
```

### Auto demo (for screen recording)
```bash
python demo_auto.py
```

---

## Programmatic API

```python
from smartstudy_agent import SmartStudyAgent

agent = SmartStudyAgent()   # uses ANTHROPIC_API_KEY env var

# Phase 1 — Observe
observed = agent.observe("Lecture text about Machine Learning...")
# {'topics': [...], 'descriptions': {...}, 'summary': '...'}

# Phase 2 — Plan
plan = agent.plan(observed)
print(plan.sequence)        # ['Linear Algebra', 'Neural Networks', ...]

# Phase 3 — Act
topic = plan.sequence[0]
questions = agent.act(topic, observed["descriptions"][topic], n=3)

# Phase 4 — Evaluate
result = agent.evaluate(questions, answers=["B", "A", "C"])
print(f"Score: {result['score']:.0%}")
print(result["feedback"])

# Phase 5 — Adapt
adaptation = agent.adapt(topic, result)
print(adaptation["action"])              # 'advance' | 'reinforce' | 'review'
print(agent.profile.summary())
```

### Supporting modules

```python
import storage
from concept_graph import ConceptGraph
from spaced_repetition import get_review_queue
from rl_policy import QLearningPolicy
from evaluation import compare

# Persistent storage
record = storage.load_student("alice")
storage.add_session("alice", {"topic": "Neural Networks", "score": 0.9})

# Concept dependency graph (topological sort)
g = ConceptGraph()
g.topological_sort(["Backpropagation", "Linear Algebra", "Neural Networks"])
# -> ['Linear Algebra', 'Neural Networks', 'Backpropagation']

# Spaced repetition scheduler (SM-2)
due_today = get_review_queue(record["quiz_history"])

# Q-learning adaptive policy
policy = QLearningPolicy()
action = policy.choose_action(score=0.55)         # 'reinforce'
policy.update(prev_score=0.55, action=action, new_score=0.80)

# Quantitative evaluation vs random baseline
results = compare(n_runs=30, n_sessions=20)
print(f"Adaptive beats baseline by {results['improvement_pct']:.1f}%")
```

---

## Web App Pages

| Page | Purpose |
|------|---------|
| 🏠 **Dashboard** | Mastered topics, weak areas, due reviews, and key metrics |
| 📖 **Study Session** | Upload a lecture and run the full OPEAA loop step-by-step |
| 🔁 **Spaced Review** | SM-2 scheduler shows what to review today |
| 🧠 **Concept Graph** | Visualizes the topic prerequisite DAG with mastered topics highlighted |
| 📊 **Progress History** | Personal score trajectory across all attempts |
| 👥 **Peer Comparison** | Multi-student leaderboard ranked by average score |
| 🎯 **RL Policy** | Inspect the Q-table and train it on simulated episodes |
| 🧪 **Baseline Evaluation** | Adaptive vs random topic-selection simulation results |

---

## Project Structure

```
smartstudy-agent/
├── smartstudy_agent.py     # Core agent — 5 OPEAA phases
├── mock_claude.py          # Offline mock client
├── app.py                  # Streamlit web app (8 pages)
├── demo.py                 # Interactive terminal demo
├── demo_auto.py            # Automated demo (no input needed)
│
├── storage.py              # JSON persistent storage
├── concept_graph.py        # Topic prerequisite DAG (Kahn's topo sort)
├── rl_policy.py            # Tabular Q-learning policy
├── spaced_repetition.py    # SM-2 review scheduler
├── multi_format.py         # PDF/TXT/MD/DOCX/PPTX/VTT/SRT loader
├── evaluation.py           # Adaptive vs baseline simulation
│
├── generate_visuals.py     # Generates architecture diagrams
├── requirements.txt        # Python dependencies
├── README.md               # This file
│
├── data/                   # Created at runtime
│   ├── students.json       # Persistent student profiles
│   └── qtable.json         # Q-learning policy state
│
└── visuals/                # Generated PNG diagrams
    ├── adaptive_loop.png
    ├── system_architecture.png
    ├── performance_dashboard.png
    └── ai_techniques.png
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Anthropic Claude (`claude-opus-4-6` with adaptive thinking) |
| Web UI | Streamlit |
| RL | Tabular Q-learning over discretized score buckets |
| Knowledge Graph | NetworkX + Kahn's algorithm |
| Spaced Repetition | SM-2 algorithm |
| Storage | JSON (zero-config, no DB required) |
| Document Parsing | pypdf, python-docx, python-pptx |
| Terminal UI | rich |

---

## How the Agent Decides

### Heuristic Policy (default)

| Quiz Score | Action | Rationale |
|------------|--------|-----------|
| ≥ 70% | `advance` | Bloom's mastery threshold met — move on |
| 50–69% | `reinforce` | Concept partially understood — practice more |
| < 50% | `review` | Foundation missing — re-read source material |

The 70% threshold is grounded in Bloom's 1968 research on mastery learning, which showed that students need ~70-80% mastery before new material consolidates effectively.

### Q-Learning Policy (alternative)

State space is discretized into 5 mastery buckets (`very_low`, `low`, `medium`, `high`, `very_high`). The Q-table is updated via standard tabular Q-learning:

```
Q(s, a) ← Q(s, a) + α · [r + γ · max(Q(s', a')) − Q(s, a)]
```

where the reward `r` is proportional to the score change between attempts. The learned policy can be inspected and trained interactively in the **🎯 RL Policy** page of the web app.

---

## Roadmap

- [x] Core 5-phase OPEAA loop with Claude
- [x] Heuristic adaptive policy (Bloom 70%)
- [x] Persistent multi-student storage
- [x] Concept dependency graph + topological sort
- [x] Q-learning adaptive policy
- [x] SM-2 spaced repetition
- [x] Streamlit web app with 8 pages
- [x] Multi-format input loader
- [x] Quantitative baseline evaluation
- [ ] Concept graph editor in the UI
- [ ] Cross-course prerequisite linking
- [ ] Real classroom pilot study
- [ ] Replace JSON storage with SQLite for >1k students
- [ ] Deploy as a hosted SaaS

---

## License

MIT License — see [LICENSE](LICENSE) for details.

```
Copyright © 2026 Haofei Sun

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction...
```

---

## Author

**Haofei Sun**

If you find this project useful, please consider giving it a ⭐ on GitHub.

For questions, suggestions, or collaboration: open an [issue](../../issues) or start a [discussion](../../discussions).

---
title: Smart Study Agent
emoji: 🎓
colorFrom: blue
colorTo: purple
sdk: streamlit
sdk_version: 1.56.0
app_file: app.py
pinned: true
license: mit
short_description: Adaptive AI study agent with OPEAA loop, RL & FSRS
---

# 🎓 Smart Study Agent

An adaptive AI study agent — a reinforcement-learning policy decides *what* you study next, an FSRS memory model decides *when* you review, and an LLM generates the quizzes in between.

## Features

- **5-phase OPEAA loop** — Observe → Plan → Act → Evaluate → Adapt
- **RL decision layer** — Q-learning + LinUCB bandit pick the action, not the LLM
- **POMDP belief state** persisted across sessions
- **FSRS spaced repetition** — per-topic recall probability, stability & due dates (same algorithm family as modern Anki)
- **🃏 Anki export** — download your generated question bank as a styled `.apkg` deck
- **Interactive concept graph** — draggable prerequisite DAG, mastery color-coded
- **Multi-format input** — PDF, TXT, MD, DOCX, PPTX, VTT, SRT
- **Multi-student support** with peer comparison
- **MCP server & Claude Agent Skill** in the [GitHub repo](https://github.com/HumphreySun98/Smart-Study-Agent) — drive the agent from Claude

## Usage

1. Create a student in the sidebar
2. Go to **📖 Study Session**
3. Click **"Use Sample ML Lecture"** or upload your own PDF
4. Run all 5 OPEAA phases in order

## Tech Stack

Streamlit · Claude API (`claude-opus-4-6`) · NetworkX + pyvis · Q-learning · FSRS (py-fsrs) · genanki

## Author

Built by **Haofei Sun** · [GitHub](https://github.com/HumphreySun98/Smart-Study-Agent) · [HF Space](https://huggingface.co/spaces/HumphreySun98/smart-study-agent)

> **Note:** This Space uses HF Inference Providers (Kimi-K2) for free LLM access.
> Local users with an `ANTHROPIC_API_KEY` can switch to Claude `claude-opus-4-6` automatically.

## License

MIT

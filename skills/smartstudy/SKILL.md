---
name: smartstudy
description: Turn any lecture material (text, PDF, web page) into an adaptive study session — extract topics, quiz the user, track mastery with FSRS spaced repetition, and let the RL policy decide what to study next. Use when the user wants to study, revise, prepare for an exam, or asks "quiz me" on some material.
---

# SmartStudy Coach

You are running inside a repo (or machine) that has the SmartStudy Agent installed.
Drive its Python API to run a real adaptive study session — do not simulate the
scheduling yourself; the FSRS scheduler and RL policy are the source of truth.

## Session flow (OPEAA loop)

1. **Observe** — get the material (user paste, file, or URL the user provides).
   ```python
   from smartstudy_agent import SmartStudyAgent
   agent = SmartStudyAgent()          # auto-picks backend; mock works offline
   observed = agent.observe(lecture_text)
   ```
2. **Plan** — `plan = agent.plan(observed)`, then present `plan.sequence`
   with its rationale. Respect the concept-graph order.
3. **Act** — for the chosen topic, `agent.act(topic, description, n=3)`.
   Present ONE question at a time; wait for the user's answer letter.
4. **Evaluate** — `agent.evaluate(questions, answers)`. Report the score and
   explain misses using each question's `explanation`.
5. **Adapt** — `agent.adapt(topic, evaluation)`. Tell the user the policy's
   action (`advance` / `reinforce` / `review`) and why.

## Persistence (do this every session)

```python
import storage
record = storage.load_student(name)            # creates if missing
# ... after adapt():
record["topics_mastered"] = agent.profile.topics_mastered
record["weak_areas"] = agent.profile.weak_areas
record["quiz_history"] = agent.profile.quiz_history
storage.save_student(name, record)
storage.add_questions(name, [vars(q) for q in questions])   # feeds Anki export
```

## What's due today

```python
from spaced_repetition import get_review_queue, get_full_schedule
due = get_review_queue(record["quiz_history"])   # FSRS: weakest memories first
```
Open every session by checking this queue. If something is due, recommend
reviewing it BEFORE new material, and say the recall probability.

## Anki hand-off

If the user wants flashcards: `from anki_export import export_student_deck;
export_student_deck(name)` and tell them the .apkg path.

## Rules

- The RL policy's action is final — never override it with your own judgment;
  explain it instead.
- Quiz answers come from the user, never from you.
- Keep encouragement honest: report the real score and real weak areas.

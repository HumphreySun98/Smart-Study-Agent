# mcp_server.py
# MCP server exposing the SmartStudy agent to Claude Desktop / Claude Code /
# any MCP client. Your AI assistant can check what's due for review, generate
# quizzes, record results (which trains the RL policy), and export Anki decks.
#
# Run (stdio):        python mcp_server.py
# Claude Code:        claude mcp add smartstudy -- python /path/to/mcp_server.py
# Claude Desktop (claude_desktop_config.json):
#   {"mcpServers": {"smartstudy": {"command": "python",
#                                  "args": ["/path/to/mcp_server.py"]}}}
#
# Requires:  pip install "mcp[cli]"
# Haofei Sun - CSE 5360

import json

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    raise SystemExit(
        "The MCP server requires the `mcp` package:  pip install \"mcp[cli]\""
    )

import storage
from spaced_repetition import get_review_queue, get_full_schedule, ALGORITHM

mcp = FastMCP(
    "smartstudy",
    instructions=(
        "SmartStudy Agent — adaptive spaced-repetition study scheduler. "
        "Use review_queue to see what a student should study now, "
        "generate_quiz to create questions, record_quiz_result after "
        "the student answers (this trains the RL policy), and "
        "export_anki_deck to hand the question bank to Anki."
    ),
)


@mcp.tool()
def list_students() -> str:
    """List all students known to SmartStudy."""
    return json.dumps(storage.list_students())


@mcp.tool()
def get_student_profile(student: str) -> str:
    """Get a student's belief state: mastered topics, weak areas, quiz count."""
    record = storage.load_student(student)
    return json.dumps({
        "name": student,
        "topics_mastered": record["topics_mastered"],
        "weak_areas": record["weak_areas"],
        "quizzes_taken": len(record["quiz_history"]),
    })


@mcp.tool()
def review_queue(student: str) -> str:
    """Topics due for review right now (FSRS memory model), plus the full
    memory-state schedule: recall probability, stability, next due date."""
    record = storage.load_student(student)
    due = get_review_queue(record["quiz_history"])
    schedule = get_full_schedule(record["quiz_history"])
    return json.dumps({
        "algorithm": ALGORITHM,
        "due_now": [
            {k: v for k, v in r.items() if k != "due"} for r in due
        ],
        "all_topics": [
            {**{k: v for k, v in r.items() if k != "due"},
             "next_due": r["due"].isoformat()} for r in schedule
        ],
    }, default=str)


@mcp.tool()
def next_action(student: str, topic: str) -> str:
    """Ask the RL policy what to do next for this student+topic:
    'advance', 'reinforce', or 'review'. Decision comes from the learned
    Q-table, not an LLM."""
    from rl_policy import QLearningPolicy
    record = storage.load_student(student)
    last_score = 0.0
    for h in reversed(record["quiz_history"]):
        if h.get("topic") == topic:
            last_score = h.get("score", 0.0)
            break
    policy = QLearningPolicy()
    action = policy.choose_action(last_score)
    return json.dumps({
        "topic": topic, "last_score": last_score,
        "action": action, "policy": "qlearning",
    })


@mcp.tool()
def generate_quiz(topic: str, description: str = "", n: int = 3) -> str:
    """Generate n multiple-choice questions on a topic using the configured
    LLM backend (Claude / custom endpoint / HF / mock)."""
    from smartstudy_agent import SmartStudyAgent
    agent = SmartStudyAgent()
    questions = agent.act(topic, description, n=n)
    return json.dumps([
        {"topic": q.topic, "question": q.question, "choices": q.choices,
         "correct_answer": q.correct_answer, "explanation": q.explanation}
        for q in questions
    ])


@mcp.tool()
def record_quiz_result(student: str, topic: str, score: float) -> str:
    """Record a quiz result (0.0-1.0). Updates the belief state, trains the
    Q-learning policy, and reschedules the topic under FSRS."""
    from smartstudy_agent import StudentProfile
    from rl_policy import QLearningPolicy

    record = storage.load_student(student)
    profile = StudentProfile(
        topics_mastered=record["topics_mastered"],
        weak_areas=record["weak_areas"],
        quiz_history=record["quiz_history"],
    )
    prev_score = 0.0
    for h in reversed(profile.quiz_history):
        if h.get("topic") == topic:
            prev_score = h.get("score", 0.0)
            break

    profile.record_quiz(topic=topic, score=score, missed=[])

    policy = QLearningPolicy()
    action = policy.choose_action(score)
    policy.update(prev_score, action, score)

    record["topics_mastered"] = profile.topics_mastered
    record["weak_areas"] = profile.weak_areas
    record["quiz_history"] = profile.quiz_history
    storage.save_student(student, record)
    storage.add_session(student, {"topic": topic, "score": score,
                                  "action": action, "n_questions": 0})

    return json.dumps({
        "recorded": True, "topic": topic, "score": score,
        "policy_action": action,
        "mastered": topic in profile.topics_mastered,
    })


@mcp.tool()
def save_quiz_to_bank(student: str, questions_json: str) -> str:
    """Save generated questions to the student's bank so they can be
    exported to Anki. questions_json = JSON array from generate_quiz."""
    questions = json.loads(questions_json)
    storage.add_questions(student, questions)
    return json.dumps({"saved": len(questions)})


@mcp.tool()
def export_anki_deck(student: str, out_path: str = None) -> str:
    """Export the student's question bank as an Anki .apkg file.
    Returns the written file path."""
    from anki_export import export_student_deck
    path = export_student_deck(student, out_path)
    return json.dumps({"path": path})


if __name__ == "__main__":
    mcp.run()

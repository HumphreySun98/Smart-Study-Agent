# demo_auto.py
# Hands-free version of demo.py — fixed answers, paced for screen recording.
# Haofei Sun - CSE 5360

import os
import time
import sys
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint

from smartstudy_agent import SmartStudyAgent

console = Console()

SAMPLE_CONTENT = """
Introduction to Machine Learning

1. Supervised Learning
Supervised learning is a type of machine learning where the model is trained on
labeled data. The algorithm learns a mapping from inputs to outputs. Common
examples include classification (predicting a category) and regression
(predicting a continuous value). Key algorithms include linear regression,
decision trees, support vector machines, and neural networks.

2. Unsupervised Learning
In unsupervised learning, the model is trained on unlabeled data and must find
hidden patterns or intrinsic structures. Clustering algorithms (e.g., k-means,
hierarchical clustering) group similar data points together. Dimensionality
reduction techniques like PCA help visualize and compress high-dimensional data.

3. Neural Networks
Neural networks are computing systems inspired by biological neural networks.
They consist of layers of interconnected nodes (neurons). Deep neural networks
have multiple hidden layers and can learn complex representations.
Backpropagation is the algorithm used to train neural networks by minimizing loss.
"""

# 2/3 correct → score 67% → triggers REINFORCE in the demo
AUTO_ANSWERS = ["B", "B", "C"]

PAUSE = 1.2


def phase_banner(name: str, description: str, color: str = "cyan"):
    time.sleep(PAUSE)
    console.print()
    console.print(Rule(f"[bold {color}]◆  Phase {name}[/bold {color}]"))
    console.print(f"  [dim]{description}[/dim]")
    console.print()
    time.sleep(0.4)


def fake_thinking(message: str, duration: float = 1.8):
    """Spinner-with-delay used during demo recordings."""
    with console.status(f"[cyan]{message}[/cyan]", spinner="dots"):
        time.sleep(duration)


def main():
    console.clear()
    time.sleep(0.5)

    # header
    console.print(Panel(
        "[bold blue]SmartStudy Agent[/bold blue]\n"
        "[white]An AI-Powered Adaptive Learning Assistant[/white]\n\n"
        "[dim]CSE 5360 Artificial Intelligence I — University of Texas at Arlington[/dim]\n"
        "[dim]Team: Haofei Sun  ·  Md Parveg Plaban  ·  Sijan Shrestha[/dim]",
        border_style="blue",
        padding=(1, 4),
    ))
    use_mock = not os.environ.get("ANTHROPIC_API_KEY")
    if use_mock:
        console.print("[yellow]⚡ Running in MOCK mode — no API key required[/yellow]\n")
    else:
        console.print("[green]✓ Running with real Claude API (claude-opus-4-6)[/green]\n")
    time.sleep(1.0)

    agent = SmartStudyAgent(mock=use_mock)

    # PHASE 1: OBSERVE
    phase_banner("1 — OBSERVE", "Reading lecture material and extracting key topics", "cyan")
    fake_thinking("Claude analyzing lecture content with adaptive thinking...", 2.0)
    observed = agent.observe(SAMPLE_CONTENT)

    table = Table(title="Extracted Topics", header_style="bold magenta", show_lines=True)
    table.add_column("Topic", style="bold cyan", min_width=24)
    table.add_column("Description")
    for topic in observed["topics"]:
        desc = observed["descriptions"].get(topic, "")
        table.add_row(topic, desc)
    console.print(table)
    console.print(Panel(observed["summary"], title="[bold]Content Summary[/bold]",
                        border_style="green"))

    # PHASE 2: PLAN
    phase_banner("2 — PLAN", "Building personalized study plan from StudentProfile belief state", "blue")
    fake_thinking("Prioritizing topics based on mastery gaps...", 1.6)
    plan = agent.plan(observed)

    table2 = Table(title="Study Plan", header_style="bold magenta", show_lines=True)
    table2.add_column("#", style="dim", width=3)
    table2.add_column("Topic", style="bold cyan")
    table2.add_column("Priority", width=10)
    pcolors = {"high": "red", "medium": "yellow", "low": "green"}
    for i, t in enumerate(plan.sequence, 1):
        p = plan.priorities.get(t, "medium")
        table2.add_row(str(i), t, f"[{pcolors[p]}]{p.upper()}[/{pcolors[p]}]")
    console.print(table2)
    console.print(Panel(plan.rationale, title="[bold]Rationale[/bold]", border_style="blue"))

    topic = plan.sequence[0]
    topic_desc = observed["descriptions"].get(topic, "")

    # PHASE 3: ACT
    phase_banner("3 — ACT", f"Generating quiz questions for: {topic}", "yellow")
    fake_thinking(f"Claude generating MCQ questions for '{topic}'...", 1.8)
    questions = agent.act(topic, topic_desc, n=3)

    console.print(Panel(
        f"[bold]Quiz — {topic}[/bold]\n[dim]3 multiple-choice questions[/dim]",
        border_style="yellow"
    ))

    for i, q in enumerate(questions, 1):
        time.sleep(0.5)
        console.print(f"\n[bold]Q{i}.[/bold] {q.question}")
        for choice in q.choices:
            console.print(f"  {choice}")
        time.sleep(0.8)
        ans = AUTO_ANSWERS[i - 1]
        console.print(f"  [bold cyan]Your answer:[/bold cyan] [bold white]{ans}[/bold white]")
        time.sleep(0.4)

    # PHASE 4: EVALUATE
    phase_banner("4 — EVALUATE", "Scoring answers and generating Claude feedback", "red")
    fake_thinking("Evaluating performance...", 1.4)
    evaluation = agent.evaluate(questions, AUTO_ANSWERS)

    score = evaluation["score"]
    color = "green" if score >= 0.7 else "yellow" if score >= 0.5 else "red"
    console.print(Panel(
        f"[bold {color}]Score: {score:.0%}[/bold {color}]  "
        f"({len(evaluation['correct'])}/{len(questions)} correct)\n\n"
        + ("⚠  Below 70% mastery threshold — reinforcement recommended" if score < 0.7
           else "✓  Mastery threshold reached — ready to advance"),
        title="Results", border_style=color
    ))

    for i, (q, ans) in enumerate(zip(questions, AUTO_ANSWERS)):
        is_correct = i in evaluation["correct"]
        icon = "[green]✓[/green]" if is_correct else "[red]✗[/red]"
        console.print(f"  {icon} Q{i+1}: answered [bold]{ans}[/bold], "
                      f"correct: [bold]{q.correct_answer}[/bold]")
        if not is_correct:
            console.print(f"    [dim]{q.explanation}[/dim]")

    console.print()
    console.print(Panel(evaluation["feedback"], title="[bold]Claude Feedback[/bold]",
                        border_style="cyan"))

    # PHASE 5: ADAPT
    phase_banner("5 — ADAPT", "Updating belief state (StudentProfile) and selecting next action", "green")
    fake_thinking("Applying adaptive policy...", 1.4)
    adaptation = agent.adapt(topic, evaluation)

    action = adaptation.get("action", "advance")
    acolors = {"review": "yellow", "reinforce": "orange3", "advance": "green"}
    ac = acolors.get(action, "white")

    console.print(Panel(
        f"[bold {ac}]Decision: {action.upper()}[/bold {ac}]\n\n"
        + (f"Next topic: [cyan]{adaptation['next_topic']}[/cyan]\n\n"
           if adaptation.get("next_topic") else "")
        + adaptation.get("recommendation", ""),
        title="Adaptive Recommendation", border_style=ac
    ))

    # show updated profile
    time.sleep(0.6)
    console.print(Panel(
        f"[bold]Updated Student Profile[/bold]\n\n{agent.profile.summary()}",
        border_style="magenta", title="Belief State (StudentProfile)"
    ))

    # session summary table
    time.sleep(PAUSE)
    console.print()
    console.print(Rule("[bold green]Session Complete[/bold green]"))
    console.print()

    summary_table = Table(title="OPEAA Loop — Session Summary", header_style="bold white",
                          show_lines=True)
    summary_table.add_column("Phase", style="bold cyan", min_width=12)
    summary_table.add_column("Input")
    summary_table.add_column("Output")
    summary_table.add_row("OBSERVE", "Lecture text (ML)",
                          f"{len(observed['topics'])} topics extracted")
    summary_table.add_row("PLAN", "StudentProfile",
                          f"{len(plan.sequence)}-topic study plan")
    summary_table.add_row("ACT", f"Topic: {topic}", "3 MCQ questions generated")
    summary_table.add_row("EVALUATE", "Student answers",
                          f"Score: {score:.0%}  |  Feedback: Claude LLM")
    summary_table.add_row("ADAPT", "Evaluation result",
                          f"Action: {action.upper()}  |  Profile updated")
    console.print(summary_table)
    console.print()


if __name__ == "__main__":
    main()

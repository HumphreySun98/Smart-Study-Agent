# demo.py
# Interactive demo for SmartStudy Agent
# Run: python demo.py --mock       (offline mode)
#      python demo.py               (real Claude API)
#      python demo.py --pdf lec.pdf (use your own lecture)
# Haofei Sun - CSE 5360

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich import print as rprint

from smartstudy_agent import SmartStudyAgent, StudyPlan, QuizQuestion

console = Console()

# sample ML lecture content used when no PDF is provided
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
(deep learning) have multiple hidden layers and can learn complex representations.
Backpropagation is the algorithm used to train neural networks by minimizing loss.

4. Overfitting and Regularization
Overfitting occurs when a model learns the training data too well, including noise,
and fails to generalize to new data. Regularization techniques (L1, L2, dropout)
penalize model complexity to improve generalization. Cross-validation helps
evaluate model performance on unseen data.

5. Evaluation Metrics
Accuracy measures the fraction of correct predictions. Precision and recall are
important for imbalanced datasets. The F1 score is the harmonic mean of precision
and recall. For regression, common metrics include mean squared error (MSE) and
mean absolute error (MAE). Confusion matrices visualize classification results.
"""


def load_pdf(path: str) -> str:
    """Try to read a PDF, fall back to sample content if pypdf isn't installed."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        return text.strip()
    except ImportError:
        console.print("[yellow]pypdf not installed — using sample content.[/yellow]")
        return SAMPLE_CONTENT


# --- display helpers ---

def print_phase(name: str, description: str):
    console.print()
    console.print(Rule(f"[bold cyan]Phase: {name}[/bold cyan]"))
    console.print(f"[dim]{description}[/dim]")
    console.print()


def display_topics(observed: dict):
    table = Table(title="Extracted Topics", show_header=True, header_style="bold magenta")
    table.add_column("Topic", style="cyan", no_wrap=True)
    table.add_column("Description")
    for topic in observed["topics"]:
        desc = observed["descriptions"].get(topic, "")
        table.add_row(topic, desc)
    console.print(table)
    console.print(Panel(observed["summary"], title="Content Summary", border_style="green"))


def display_plan(plan: StudyPlan):
    table = Table(title="Study Plan", show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=3)
    table.add_column("Topic", style="cyan")
    table.add_column("Priority")

    priority_color = {"high": "red", "medium": "yellow", "low": "green"}
    for i, topic in enumerate(plan.sequence, 1):
        p = plan.priorities.get(topic, "medium")
        color = priority_color.get(p, "white")
        table.add_row(str(i), topic, f"[{color}]{p.upper()}[/{color}]")
    console.print(table)
    console.print(Panel(plan.rationale, title="Rationale", border_style="blue"))


def run_quiz(questions: list[QuizQuestion]) -> list[str]:
    """Show questions one by one and collect student answers."""
    answers = []
    console.print(Panel(
        f"[bold]Quiz — {questions[0].topic}[/bold]\n"
        "Answer each question with A, B, C, or D.",
        border_style="yellow"
    ))
    for i, q in enumerate(questions, 1):
        console.print(f"\n[bold]Q{i}.[/bold] {q.question}")
        for choice in q.choices:
            console.print(f"  {choice}")
        while True:
            ans = console.input("  [bold cyan]Your answer:[/bold cyan] ").strip().upper()
            if ans and ans[0] in "ABCD":
                answers.append(ans[0])
                break
            console.print("  [red]Please enter A, B, C, or D.[/red]")
    return answers


def display_evaluation(evaluation: dict, questions: list[QuizQuestion], answers: list[str]):
    score = evaluation["score"]
    color = "green" if score >= 0.7 else "red" if score < 0.5 else "yellow"

    console.print(Panel(
        f"[bold {color}]Score: {score:.0%}[/bold {color}]  "
        f"({len(evaluation['correct'])}/{len(questions)} correct)",
        title="Results",
        border_style=color
    ))

    for i, (q, ans) in enumerate(zip(questions, answers)):
        is_correct = i in evaluation["correct"]
        icon = "[green]✓[/green]" if is_correct else "[red]✗[/red]"
        console.print(f"  {icon} Q{i+1}: you answered [bold]{ans}[/bold], "
                      f"correct: [bold]{q.correct_answer}[/bold]")
        if not is_correct:
            console.print(f"    [dim]{q.explanation}[/dim]")

    console.print()
    console.print(Panel(evaluation["feedback"], title="Feedback", border_style="cyan"))


def display_adaptation(adaptation: dict):
    action_color = {"review": "yellow", "reinforce": "orange3", "advance": "green"}
    action = adaptation.get("action", "advance")
    color = action_color.get(action, "white")

    console.print(Panel(
        f"[bold {color}]Recommended action: {action.upper()}[/bold {color}]\n\n"
        + (f"Next topic: [cyan]{adaptation['next_topic']}[/cyan]\n\n"
           if adaptation.get("next_topic") else "")
        + adaptation.get("recommendation", ""),
        title="Adaptive Recommendation",
        border_style=color
    ))


# --- main ---

def main():
    parser = argparse.ArgumentParser(description="SmartStudy Agent Demo")
    parser.add_argument("--pdf", help="Path to a lecture PDF", default=None)
    parser.add_argument("--topic-index", type=int, default=0,
                        help="Which topic to quiz on (0-based index)")
    parser.add_argument("--mock", action="store_true",
                        help="Run with mock Claude (no API key needed)")
    args = parser.parse_args()

    console.print(Panel(
        "[bold blue]SmartStudy Agent[/bold blue]\n"
        "An AI Agent for Personalized Learning\n\n"
        "CSE 5360 Artificial Intelligence I — UTA\n"
        "Team: Haofei Sun · Md Parveg Plaban · Sijan Shrestha",
        border_style="blue"
    ))

    # load lecture content
    if args.pdf and Path(args.pdf).exists():
        console.print(f"[dim]Loading PDF: {args.pdf}[/dim]")
        content = load_pdf(args.pdf)
    else:
        console.print("[dim]Using built-in sample lecture on Machine Learning.[/dim]")
        content = SAMPLE_CONTENT

    if args.mock:
        console.print("[yellow]⚡ Running in MOCK mode (no API key required)[/yellow]")
    agent = SmartStudyAgent(mock=args.mock)

    # Phase 1: OBSERVE
    print_phase("OBSERVE", "Analyzing lecture material and extracting key topics...")
    with console.status("[cyan]Extracting topics from content...[/cyan]"):
        observed = agent.observe(content)
    display_topics(observed)

    # Phase 2: PLAN
    print_phase("PLAN", "Generating a personalised study plan...")
    with console.status("[cyan]Building study plan...[/cyan]"):
        plan = agent.plan(observed)
    display_plan(plan)

    # pick which topic to quiz on
    if args.topic_index < len(plan.sequence):
        topic = plan.sequence[args.topic_index]
    else:
        topic = plan.sequence[0]
    topic_desc = observed["descriptions"].get(topic, "")

    if not console.input(
        f"\nReady to take a quiz on [bold cyan]{topic}[/bold cyan]? (Y/n): "
    ).strip().lower() in ("n", "no"):

        # Phase 3: ACT
        print_phase("ACT", f"Generating quiz questions for: {topic}")
        with console.status("[cyan]Generating quiz...[/cyan]"):
            questions = agent.act(topic, topic_desc, n=3)

        answers = run_quiz(questions)

        # Phase 4: EVALUATE
        print_phase("EVALUATE", "Scoring your answers and generating feedback...")
        with console.status("[cyan]Evaluating performance...[/cyan]"):
            evaluation = agent.evaluate(questions, answers)
        display_evaluation(evaluation, questions, answers)

        # Phase 5: ADAPT
        print_phase("ADAPT", "Updating your learning profile and recommending next steps...")
        with console.status("[cyan]Adapting recommendations...[/cyan]"):
            adaptation = agent.adapt(topic, evaluation)
        display_adaptation(adaptation)

        console.print()
        console.print(Panel(
            f"[bold]Updated Student Profile[/bold]\n\n{agent.profile.summary()}",
            border_style="magenta",
            title="Learning Profile"
        ))

    console.print()
    console.print(Rule("[dim]End of SmartStudy Session[/dim]"))


if __name__ == "__main__":
    main()

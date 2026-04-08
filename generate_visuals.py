# generate_visuals.py
# Makes the PNG diagrams for our presentation slides
# Outputs to ./visuals/
# Haofei Sun - CSE 5360

import matplotlib
matplotlib.use("Agg")   # non-interactive backend — works without a display

import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import matplotlib.patheffects as pe

os.makedirs("visuals", exist_ok=True)

BLUE   = "#2563EB"
TEAL   = "#0891B2"
GREEN  = "#16A34A"
ORANGE = "#EA580C"
PURPLE = "#7C3AED"
RED    = "#DC2626"
GRAY   = "#6B7280"
LIGHT  = "#F1F5F9"
WHITE  = "#FFFFFF"

# ─────────────────────────────────────────────────────────────────────────────
# 1. Adaptive Learning Loop (circular diagram)
# ─────────────────────────────────────────────────────────────────────────────
def draw_loop():
    fig, ax = plt.subplots(figsize=(8, 8), facecolor=WHITE)
    ax.set_aspect("equal")
    ax.axis("off")

    phases = [
        ("OBSERVE",  "Analyze lecture\nmaterials",        BLUE,   0),
        ("PLAN",     "Generate\nstudy plan",              TEAL,   72),
        ("ACT",      "Create quizzes\n& exercises",       GREEN,  144),
        ("EVALUATE", "Score student\nperformance",        ORANGE, 216),
        ("ADAPT",    "Adjust learning\nrecommendations",  PURPLE, 288),
    ]

    R = 2.6          # node centre radius
    r_node = 0.72    # node circle radius

    # Draw arc arrows between nodes
    n = len(phases)
    for i in range(n):
        a0 = np.radians(90 - phases[i][3])
        a1 = np.radians(90 - phases[(i+1) % n][3])
        # midpoint angle
        mid = (a0 + a1) / 2
        # draw dashed arc segment
        angles = np.linspace(a0, a1, 60)
        xs = R * np.cos(angles)
        ys = R * np.sin(angles)
        ax.plot(xs[4:-4], ys[4:-4], color=GRAY, lw=1.8,
                linestyle="--", alpha=0.5, zorder=1)
        # arrowhead at end
        dx = xs[-5] - xs[-6]; dy = ys[-5] - ys[-6]
        ax.annotate("", xy=(xs[-5], ys[-5]),
                    xytext=(xs[-5]-dx*0.01, ys[-5]-dy*0.01),
                    arrowprops=dict(arrowstyle="-|>", color=GRAY,
                                   lw=1.5, mutation_scale=14))

    # Draw nodes
    for label, sub, color, deg in phases:
        ang = np.radians(90 - deg)
        cx, cy = R * np.cos(ang), R * np.sin(ang)

        # outer glow ring
        ring = plt.Circle((cx, cy), r_node + 0.08, color=color, alpha=0.18, zorder=2)
        ax.add_patch(ring)

        # main circle
        circle = plt.Circle((cx, cy), r_node, color=color, zorder=3)
        ax.add_patch(circle)

        # phase name
        ax.text(cx, cy + 0.18, label, ha="center", va="center",
                fontsize=11, fontweight="bold", color=WHITE, zorder=4)
        # sub-label
        ax.text(cx, cy - 0.22, sub, ha="center", va="center",
                fontsize=7.5, color=WHITE, alpha=0.92,
                linespacing=1.4, zorder=4)

    # Centre label
    ax.text(0, 0.12, "SmartStudy", ha="center", va="center",
            fontsize=14, fontweight="bold", color=BLUE)
    ax.text(0, -0.18, "Adaptive Loop", ha="center", va="center",
            fontsize=10, color=GRAY)

    ax.set_xlim(-4, 4)
    ax.set_ylim(-4, 4)
    plt.tight_layout()
    plt.savefig("visuals/adaptive_loop.png", dpi=180, bbox_inches="tight",
                facecolor=WHITE)
    plt.close()
    print("✓ adaptive_loop.png")


# ─────────────────────────────────────────────────────────────────────────────
# 2. System Architecture (vertical flow diagram)
# ─────────────────────────────────────────────────────────────────────────────
def draw_architecture():
    fig, ax = plt.subplots(figsize=(9, 11), facecolor=WHITE)
    ax.axis("off")

    layers = [
        # (label, sublabel, bg, fg, y)
        ("Lecture Materials",   "PDF / Slides / Text Notes",        "#DBEAFE", BLUE,   9.2),
        ("Content Analyzer",    "NLP — extract text from PDF",      "#DCFCE7", GREEN,  7.8),
        ("OBSERVE",             "Claude: key topics + descriptions", BLUE,    WHITE,  6.4),
        ("PLAN",                "Claude: prioritised study plan",    TEAL,    WHITE,  5.3),
        ("ACT",                 "Claude: generate quiz questions",   GREEN,   WHITE,  4.2),
        ("EVALUATE",            "Score answers  ·  identify gaps",  ORANGE,  WHITE,  3.1),
        ("ADAPT",               "Update StudentProfile · recommend", PURPLE,  WHITE,  2.0),
        ("Student Dashboard",   "Personalised feedback & next steps","#FEF3C7",ORANGE, 0.8),
    ]

    box_w, box_h = 7.0, 0.88

    for label, sub, bg, fg, y in layers:
        # box
        rect = FancyBboxPatch((1.0, y - box_h/2), box_w, box_h,
                              boxstyle="round,pad=0.08",
                              facecolor=bg, edgecolor="#CBD5E1", linewidth=1.2)
        ax.add_patch(rect)

        # label
        ax.text(1.38, y + 0.06, label, va="center",
                fontsize=11, fontweight="bold", color=fg if fg != WHITE else "#1E293B")
        ax.text(1.38, y - 0.24, sub, va="center",
                fontsize=8.5, color=GRAY)

        # arrow down
        if y > 0.8:
            next_y = layers[layers.index((label, sub, bg, fg, y)) + 1][4]
            ax.annotate("", xy=(4.5, next_y + box_h/2 + 0.04),
                        xytext=(4.5, y - box_h/2 - 0.04),
                        arrowprops=dict(arrowstyle="-|>", color="#94A3B8",
                                        lw=1.6, mutation_scale=13))

    # Feedback loop arrow on right
    ax.annotate("", xy=(8.3, 6.4), xytext=(8.3, 2.0),
                arrowprops=dict(arrowstyle="<|-|>", color=PURPLE,
                                lw=1.8, mutation_scale=13,
                                connectionstyle="arc3,rad=0.0"))
    ax.text(8.55, 4.2, "Feedback\nLoop", ha="center", va="center",
            fontsize=8.5, color=PURPLE, rotation=90)

    ax.set_xlim(0, 9.5)
    ax.set_ylim(-0.1, 10.2)
    ax.set_title("SmartStudy Agent — System Architecture",
                 fontsize=14, fontweight="bold", color="#1E293B", pad=12)
    plt.tight_layout()
    plt.savefig("visuals/system_architecture.png", dpi=180, bbox_inches="tight",
                facecolor=WHITE)
    plt.close()
    print("✓ system_architecture.png")


# ─────────────────────────────────────────────────────────────────────────────
# 3. Student Performance Chart (bar + line)
# ─────────────────────────────────────────────────────────────────────────────
def draw_performance():
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), facecolor=WHITE)

    # ── Left: quiz scores across sessions ──
    ax = axes[0]
    sessions = ["Session 1\nNeural Nets", "Session 2\nOverfitting",
                "Session 3\nNeural Nets\n(retry)", "Session 4\nSupervised\nLearning"]
    scores = [40, 67, 90, 80]
    colors = [RED if s < 70 else GREEN if s >= 80 else ORANGE for s in scores]

    bars = ax.bar(sessions, scores, color=colors, width=0.55,
                  edgecolor="white", linewidth=1.5, zorder=3)
    ax.axhline(70, color=GRAY, linewidth=1.4, linestyle="--", label="Pass threshold (70%)", zorder=2)
    ax.plot(sessions, scores, "o-", color=BLUE, linewidth=2,
            markersize=7, zorder=4, label="Score trend")

    for bar, score in zip(bars, scores):
        ax.text(bar.get_x() + bar.get_width()/2, score + 2,
                f"{score}%", ha="center", va="bottom",
                fontsize=10, fontweight="bold",
                color=RED if score < 70 else GREEN if score >= 80 else ORANGE)

    ax.set_ylim(0, 110)
    ax.set_ylabel("Quiz Score (%)", fontsize=11)
    ax.set_title("Student Quiz Scores Over Sessions", fontsize=12, fontweight="bold")
    ax.legend(fontsize=9)
    ax.set_facecolor(LIGHT)
    ax.grid(axis="y", alpha=0.4, zorder=1)
    ax.spines[["top","right"]].set_visible(False)

    # ── Right: topics mastery radar-style bar ──
    ax2 = axes[1]
    topics = ["Neural\nNetworks", "Overfitting\n& Reg.", "Supervised\nLearning",
              "Unsupervised\nLearning", "Evaluation\nMetrics"]
    mastery = [90, 67, 80, 45, 55]
    bar_colors = [GREEN if m >= 70 else RED if m < 50 else ORANGE for m in mastery]

    ax2.barh(topics, mastery, color=bar_colors, height=0.5,
             edgecolor="white", linewidth=1.2, zorder=3)
    ax2.axvline(70, color=GRAY, linewidth=1.4, linestyle="--",
                label="Mastery threshold", zorder=2)

    for i, m in enumerate(mastery):
        ax2.text(m + 1.5, i, f"{m}%", va="center", fontsize=10, fontweight="bold",
                 color=GREEN if m >= 70 else RED if m < 50 else ORANGE)

    ax2.set_xlim(0, 105)
    ax2.set_xlabel("Mastery Level (%)", fontsize=11)
    ax2.set_title("Topic Mastery Profile", fontsize=12, fontweight="bold")
    ax2.legend(fontsize=9, loc="lower right")
    ax2.set_facecolor(LIGHT)
    ax2.grid(axis="x", alpha=0.4, zorder=1)
    ax2.spines[["top","right"]].set_visible(False)

    # legend patches
    legend_elements = [
        mpatches.Patch(color=GREEN, label="Mastered (≥80%)"),
        mpatches.Patch(color=ORANGE, label="Progressing (70–79%)"),
        mpatches.Patch(color=RED, label="Needs review (<70%)"),
    ]
    fig.legend(handles=legend_elements, loc="lower center", ncol=3,
               fontsize=9.5, frameon=False, bbox_to_anchor=(0.5, -0.04))

    plt.suptitle("SmartStudy Agent — Student Performance Dashboard",
                 fontsize=13, fontweight="bold", color="#1E293B", y=1.02)
    plt.tight_layout()
    plt.savefig("visuals/performance_dashboard.png", dpi=180, bbox_inches="tight",
                facecolor=WHITE)
    plt.close()
    print("✓ performance_dashboard.png")


# ─────────────────────────────────────────────────────────────────────────────
# 4. AI Techniques overview (icon grid)
# ─────────────────────────────────────────────────────────────────────────────
def draw_ai_techniques():
    fig, ax = plt.subplots(figsize=(11, 5), facecolor=WHITE)
    ax.axis("off")

    techniques = [
        ("Natural Language\nProcessing", "Extracts topics &\nkey concepts from text",      BLUE,   0),
        ("Large Language\nModels (LLM)",  "Claude API drives\nall reasoning phases",        TEAL,   1),
        ("Knowledge\nRepresentation",    "Structured topic\ngraphs & descriptions",        GREEN,  2),
        ("Adaptive Learning\nPolicy",    "Adjusts plan based\non quiz performance",        ORANGE, 3),
        ("Human-in-the-Loop",            "Student answers guide\nthe adaptation cycle",   PURPLE, 4),
    ]

    cols = len(techniques)
    spacing = 10.0 / cols

    for label, desc, color, i in techniques:
        cx = spacing/2 + i * spacing
        cy = 2.8

        # card background
        rect = FancyBboxPatch((cx - 0.9, 0.3), 1.8, 4.4,
                              boxstyle="round,pad=0.15",
                              facecolor=color + "18", edgecolor=color,
                              linewidth=1.8)
        ax.add_patch(rect)

        # coloured header bar
        top = FancyBboxPatch((cx - 0.9, 4.0), 1.8, 0.75,
                             boxstyle="round,pad=0.0",
                             facecolor=color, edgecolor="none")
        ax.add_patch(top)

        ax.text(cx, 4.38, label, ha="center", va="center",
                fontsize=9.5, fontweight="bold", color=WHITE, linespacing=1.35)
        ax.text(cx, 2.2, desc, ha="center", va="center",
                fontsize=8.5, color="#334155", linespacing=1.45)

    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5.5)
    ax.set_title("AI Techniques Powering SmartStudy Agent",
                 fontsize=13, fontweight="bold", color="#1E293B", pad=10)
    plt.tight_layout()
    plt.savefig("visuals/ai_techniques.png", dpi=180, bbox_inches="tight",
                facecolor=WHITE)
    plt.close()
    print("✓ ai_techniques.png")


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    draw_loop()
    draw_architecture()
    draw_performance()
    draw_ai_techniques()
    print("\nAll visuals saved to ./visuals/")

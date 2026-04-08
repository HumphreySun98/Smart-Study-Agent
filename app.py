# app.py
# SmartStudy Agent - Web UI built with Streamlit
# Includes all features: persistent profiles, multi-student, history,
# spaced repetition, concept graph, RL policy, multi-format input,
# baseline evaluation, peer dashboard
#
# Run:  streamlit run app.py
#
# Haofei Sun - CSE 5360

import os
import tempfile
from datetime import datetime

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

from smartstudy_agent import SmartStudyAgent, StudentProfile
import storage
from concept_graph import ConceptGraph
from spaced_repetition import get_review_queue
from rl_policy import QLearningPolicy
from multi_format import load_any
from evaluation import compare


# ---- page config ----

st.set_page_config(
    page_title="SmartStudy Agent",
    page_icon="📚",
    layout="wide",
)


# ---- session state init ----

def init_state():
    defaults = {
        "current_student": None,
        "agent": None,
        "observed": None,
        "plan": None,
        "questions": None,
        "answers": None,
        "evaluation": None,
        "adaptation": None,
        "lecture_text": "",
        "use_mock": not os.environ.get("ANTHROPIC_API_KEY"),
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()


# ---- helper to rebuild the agent and load profile from disk ----

def get_agent():
    if st.session_state.agent is None and st.session_state.current_student:
        agent = SmartStudyAgent(mock=st.session_state.use_mock)
        record = storage.load_student(st.session_state.current_student)
        agent.profile = StudentProfile(
            topics_mastered=record.get("topics_mastered", []),
            weak_areas=record.get("weak_areas", []),
            quiz_history=record.get("quiz_history", []),
        )
        st.session_state.agent = agent
    return st.session_state.agent


def persist_profile():
    """Write the in-memory profile back to disk."""
    if not st.session_state.current_student or st.session_state.agent is None:
        return
    record = storage.load_student(st.session_state.current_student)
    record["topics_mastered"] = st.session_state.agent.profile.topics_mastered
    record["weak_areas"] = st.session_state.agent.profile.weak_areas
    record["quiz_history"] = st.session_state.agent.profile.quiz_history
    storage.save_student(st.session_state.current_student, record)


# ---- sidebar: student picker + nav ----

with st.sidebar:
    st.title("📚 SmartStudy")
    st.caption("Adaptive Learning Agent")
    st.divider()

    # student selection
    students = storage.list_students()
    options = ["+ New Student"] + students
    pick = st.selectbox("Select Student", options,
                        index=0 if not st.session_state.current_student
                        else options.index(st.session_state.current_student)
                        if st.session_state.current_student in students else 0)

    if pick == "+ New Student":
        new_name = st.text_input("Name", key="new_student_name")
        if st.button("Create", use_container_width=True) and new_name.strip():
            storage.load_student(new_name.strip())
            st.session_state.current_student = new_name.strip()
            st.session_state.agent = None
            st.rerun()
    else:
        if pick != st.session_state.current_student:
            st.session_state.current_student = pick
            st.session_state.agent = None
            st.rerun()

    if st.session_state.current_student:
        st.success(f"👤 {st.session_state.current_student}")

    st.divider()

    # API mode indicator
    if st.session_state.use_mock:
        st.warning("Mock mode (no API key)")
    else:
        st.success("Real Claude API")

    st.divider()

    # navigation
    page = st.radio("Navigate", [
        "🏠 Dashboard",
        "📖 Study Session",
        "🔁 Spaced Review",
        "🧠 Concept Graph",
        "📊 Progress History",
        "👥 Peer Comparison",
        "🎯 RL Policy",
        "🧪 Baseline Evaluation",
    ])


# ---- helpful banner if no student selected ----

if not st.session_state.current_student:
    st.title("Welcome to SmartStudy Agent")
    st.info("👈 Create or select a student in the sidebar to begin.")
    st.stop()


# ============================================================
# PAGE: Dashboard
# ============================================================

if page == "🏠 Dashboard":
    st.title(f"Welcome back, {st.session_state.current_student}")

    record = storage.load_student(st.session_state.current_student)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Topics Mastered", len(record["topics_mastered"]))
    col2.metric("Weak Areas", len(record["weak_areas"]))
    col3.metric("Quizzes Taken", len(record["quiz_history"]))

    avg_score = (
        sum(q["score"] for q in record["quiz_history"]) / len(record["quiz_history"])
        if record["quiz_history"] else 0
    )
    col4.metric("Average Score", f"{avg_score:.0%}")

    st.divider()

    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("✓ Mastered Topics")
        if record["topics_mastered"]:
            for t in record["topics_mastered"]:
                st.markdown(f"- {t}")
        else:
            st.caption("No topics mastered yet — start a study session!")

    with col_r:
        st.subheader("⚠ Weak Areas")
        if record["weak_areas"]:
            for t in record["weak_areas"]:
                st.markdown(f"- {t}")
        else:
            st.caption("No weak areas identified yet.")

    # due reviews
    st.divider()
    st.subheader("🔁 Due for Review Today")
    review_queue = get_review_queue(record["quiz_history"])
    if review_queue:
        df = pd.DataFrame(review_queue)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.caption("Nothing due for review today.")


# ============================================================
# PAGE: Study Session
# ============================================================

elif page == "📖 Study Session":
    st.title("📖 Study Session")
    agent = get_agent()

    # ---- step 1: load lecture content ----
    st.subheader("1. Load Lecture Content")

    col_a, col_b = st.columns(2)

    with col_a:
        uploaded = st.file_uploader(
            "Upload a lecture file",
            type=["pdf", "txt", "md", "vtt", "srt", "docx", "pptx"],
        )
        if uploaded:
            with tempfile.NamedTemporaryFile(delete=False, suffix=uploaded.name) as tmp:
                tmp.write(uploaded.read())
                tmp_path = tmp.name
            try:
                st.session_state.lecture_text = load_any(tmp_path)
                st.success(f"Loaded {len(st.session_state.lecture_text)} characters")
            finally:
                os.unlink(tmp_path)

    with col_b:
        if st.button("Use Sample ML Lecture", use_container_width=True):
            from demo import SAMPLE_CONTENT
            st.session_state.lecture_text = SAMPLE_CONTENT
            st.success("Sample ML lecture loaded")

    if st.session_state.lecture_text:
        with st.expander("Preview lecture text"):
            st.text(st.session_state.lecture_text[:1500] + "...")

    st.divider()

    # ---- step 2: run OPEAA loop ----
    st.subheader("2. Run the OPEAA Loop")

    if not st.session_state.lecture_text:
        st.info("Load a lecture above first.")
        st.stop()

    # Phase 1: OBSERVE
    if st.button("▶ Phase 1: Observe", use_container_width=True):
        with st.spinner("Extracting topics..."):
            st.session_state.observed = agent.observe(st.session_state.lecture_text)
            st.session_state.plan = None
            st.session_state.questions = None

    if st.session_state.observed:
        with st.expander("📋 Phase 1: OBSERVE — Extracted Topics", expanded=True):
            for t in st.session_state.observed["topics"]:
                desc = st.session_state.observed["descriptions"].get(t, "")
                st.markdown(f"**{t}** — {desc}")
            st.info(st.session_state.observed["summary"])

        # Phase 2: PLAN
        if st.button("▶ Phase 2: Plan", use_container_width=True):
            with st.spinner("Building study plan..."):
                plan = agent.plan(st.session_state.observed)
                # apply concept graph to reorder
                graph = ConceptGraph()
                plan.sequence = graph.topological_sort(plan.sequence)
                st.session_state.plan = plan

    if st.session_state.plan:
        with st.expander("📋 Phase 2: PLAN — Study Plan", expanded=True):
            df = pd.DataFrame({
                "#": range(1, len(st.session_state.plan.sequence) + 1),
                "Topic": st.session_state.plan.sequence,
                "Priority": [st.session_state.plan.priorities.get(t, "medium").upper()
                             for t in st.session_state.plan.sequence],
            })
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.info(st.session_state.plan.rationale)

        # pick topic for quiz
        topic = st.selectbox("Pick a topic to quiz on:",
                             st.session_state.plan.sequence)

        # Phase 3: ACT
        if st.button("▶ Phase 3: Generate Quiz", use_container_width=True):
            with st.spinner(f"Creating questions for {topic}..."):
                desc = st.session_state.observed["descriptions"].get(topic, "")
                st.session_state.questions = agent.act(topic, desc, n=3)
                st.session_state.answers = None

    if st.session_state.questions:
        st.subheader("📝 Phase 3: Quiz")
        answers = []
        for i, q in enumerate(st.session_state.questions):
            st.markdown(f"**Q{i+1}.** {q.question}")
            choice = st.radio("Choose:", q.choices,
                              key=f"q_{i}",
                              label_visibility="collapsed")
            answers.append(choice[0] if choice else "A")
        st.session_state.answers = answers

        # Phase 4: EVALUATE
        if st.button("▶ Phase 4: Submit & Evaluate", use_container_width=True):
            with st.spinner("Scoring..."):
                st.session_state.evaluation = agent.evaluate(
                    st.session_state.questions, st.session_state.answers
                )

    if st.session_state.evaluation:
        ev = st.session_state.evaluation
        score = ev["score"]
        st.subheader("📊 Phase 4: Evaluation")
        col1, col2 = st.columns([1, 2])
        col1.metric("Score", f"{score:.0%}",
                    delta="Above threshold" if score >= 0.7 else "Below threshold",
                    delta_color="normal" if score >= 0.7 else "inverse")
        col2.info(ev["feedback"])

        for i, q in enumerate(st.session_state.questions):
            ans = st.session_state.answers[i]
            ok = i in ev["correct"]
            icon = "✅" if ok else "❌"
            st.markdown(f"{icon} **Q{i+1}** — your answer: `{ans}` · correct: `{q.correct_answer}`")
            if not ok:
                st.caption(q.explanation)

        # Phase 5: ADAPT
        if st.button("▶ Phase 5: Adapt & Save", use_container_width=True):
            topic = st.session_state.questions[0].topic
            with st.spinner("Updating profile..."):
                st.session_state.adaptation = agent.adapt(topic, ev)

            # save back to disk
            persist_profile()
            storage.add_session(st.session_state.current_student, {
                "topic": topic,
                "score": ev["score"],
                "action": st.session_state.adaptation.get("action"),
                "n_questions": len(st.session_state.questions),
            })
            st.success("Session saved!")

    if st.session_state.adaptation:
        ad = st.session_state.adaptation
        st.subheader("🎯 Phase 5: Adaptation")
        st.info(f"**Action:** {ad.get('action', '').upper()}\n\n"
                f"**Next topic:** {ad.get('next_topic', 'N/A')}\n\n"
                f"{ad.get('recommendation', '')}")


# ============================================================
# PAGE: Spaced Review
# ============================================================

elif page == "🔁 Spaced Review":
    st.title("🔁 Spaced Repetition Schedule")
    st.caption("Topics due for review based on SM-2 algorithm")

    record = storage.load_student(st.session_state.current_student)
    queue = get_review_queue(record["quiz_history"])

    if not queue:
        st.info("Nothing due for review yet. Take some quizzes first!")
    else:
        for item in queue:
            urgency = "🔴" if item["days_overdue"] > 3 else "🟡" if item["days_overdue"] > 0 else "🟢"
            st.markdown(
                f"{urgency} **{item['topic']}** — last score {item['last_score']:.0%}, "
                f"{item['days_overdue']} day(s) overdue · last seen {item['last_seen']}"
            )


# ============================================================
# PAGE: Concept Graph
# ============================================================

elif page == "🧠 Concept Graph":
    st.title("🧠 Concept Dependency Graph")
    st.caption("Prerequisites between AI/ML topics")

    graph = ConceptGraph()
    record = storage.load_student(st.session_state.current_student)
    mastered = set(record["topics_mastered"])

    # render with matplotlib
    try:
        import networkx as nx
        G = nx.DiGraph()
        for prereq, topic in graph.to_edges():
            G.add_edge(prereq, topic)

        fig, ax = plt.subplots(figsize=(12, 8))
        pos = nx.spring_layout(G, k=2, seed=42)
        node_colors = ["#16A34A" if n in mastered else "#94A3B8" for n in G.nodes()]
        nx.draw(G, pos, with_labels=True, node_color=node_colors,
                node_size=2200, font_size=8, font_weight="bold",
                edge_color="#64748B", arrows=True, arrowsize=15, ax=ax)
        st.pyplot(fig)
    except ImportError:
        st.warning("Install `networkx` for graph visualization. Showing as table:")
        edges_df = pd.DataFrame(graph.to_edges(), columns=["Prerequisite", "Topic"])
        st.dataframe(edges_df, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Your missing prerequisites")
    for topic in graph.prereqs:
        missing = graph.missing_prereqs(topic, list(mastered))
        if missing and topic not in mastered:
            st.markdown(f"**{topic}** needs: {', '.join(missing)}")


# ============================================================
# PAGE: Progress History
# ============================================================

elif page == "📊 Progress History":
    st.title("📊 Your Progress")
    record = storage.load_student(st.session_state.current_student)
    history = record["quiz_history"]

    if not history:
        st.info("No quiz history yet.")
    else:
        df = pd.DataFrame(history)
        df["attempt"] = range(1, len(df) + 1)
        df["score_pct"] = df["score"] * 100

        # line chart of scores
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(df["attempt"], df["score_pct"], "o-", color="#2563EB", linewidth=2)
        ax.axhline(70, color="gray", linestyle="--", label="Mastery threshold")
        ax.set_xlabel("Attempt #")
        ax.set_ylabel("Score (%)")
        ax.set_ylim(0, 105)
        ax.legend()
        ax.grid(alpha=0.3)
        st.pyplot(fig)

        # raw history table
        st.subheader("Quiz History")
        st.dataframe(df[["attempt", "topic", "score_pct"]],
                     use_container_width=True, hide_index=True)


# ============================================================
# PAGE: Peer Comparison
# ============================================================

elif page == "👥 Peer Comparison":
    st.title("👥 Peer Comparison Dashboard")

    all_students = storage.list_students()
    rows = []
    for name in all_students:
        rec = storage.load_student(name)
        n_quizzes = len(rec["quiz_history"])
        avg = (sum(q["score"] for q in rec["quiz_history"]) / n_quizzes
               if n_quizzes else 0)
        rows.append({
            "Student": name,
            "Quizzes Taken": n_quizzes,
            "Topics Mastered": len(rec["topics_mastered"]),
            "Avg Score": f"{avg:.0%}",
            "Avg Score Raw": avg,
        })

    if not rows:
        st.info("No students yet.")
    else:
        df = pd.DataFrame(rows).sort_values("Avg Score Raw", ascending=False)
        df = df.drop(columns=["Avg Score Raw"])
        df.insert(0, "Rank", range(1, len(df) + 1))
        st.dataframe(df, use_container_width=True, hide_index=True)


# ============================================================
# PAGE: RL Policy
# ============================================================

elif page == "🎯 RL Policy":
    st.title("🎯 Reinforcement Learning Policy")
    st.caption("Q-learning policy that adapts to student behavior")

    policy = QLearningPolicy()

    st.subheader("Current Q-Table")
    q_df = pd.DataFrame(policy.q).T
    st.dataframe(q_df, use_container_width=True)

    st.subheader("Best Action per State")
    summary = policy.policy_summary()
    sum_df = pd.DataFrame(list(summary.items()),
                          columns=["State (mastery)", "Best Action"])
    st.dataframe(sum_df, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("Train the Policy")
    st.caption("Simulate a sequence of quizzes to update Q-values")
    if st.button("Run 50 training episodes"):
        import random
        prog = st.progress(0)
        for i in range(50):
            prev = random.random()
            action = policy.choose_action(prev)
            new = min(1.0, prev + random.uniform(-0.2, 0.3))
            policy.update(prev, action, new)
            prog.progress((i + 1) / 50)
        st.success("Training complete! Refresh the page to see updated policy.")


# ============================================================
# PAGE: Baseline Evaluation
# ============================================================

elif page == "🧪 Baseline Evaluation":
    st.title("🧪 Adaptive vs Baseline Evaluation")
    st.caption("Quantitative comparison of our agent against random topic selection")

    n_runs = st.slider("Number of simulation runs", 10, 100, 30)
    n_sessions = st.slider("Sessions per run", 5, 50, 20)

    if st.button("Run Comparison", use_container_width=True):
        with st.spinner("Simulating..."):
            results = compare(n_runs=n_runs, n_sessions=n_sessions)

        col1, col2, col3 = st.columns(3)
        col1.metric("Baseline Avg",
                    f"{results['baseline']['mean']:.1%}",
                    f"±{results['baseline']['std']:.2%}")
        col2.metric("Adaptive Avg",
                    f"{results['adaptive']['mean']:.1%}",
                    f"±{results['adaptive']['std']:.2%}")
        col3.metric("Improvement",
                    f"+{results['improvement_pct']:.1f}%",
                    delta_color="normal")

        # plot distribution
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.hist(results["baseline"]["all"], bins=15, alpha=0.6,
                label="Baseline (random)", color="#94A3B8")
        ax.hist(results["adaptive"]["all"], bins=15, alpha=0.6,
                label="Adaptive (ours)", color="#2563EB")
        ax.set_xlabel("Average score per run")
        ax.set_ylabel("Frequency")
        ax.legend()
        ax.grid(alpha=0.3)
        st.pyplot(fig)

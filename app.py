# app.py
# Streamlit web UI for the SmartStudy Agent.
# Run:  streamlit run app.py
# Haofei Sun - CSE 5360

import os
import tempfile
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

from smartstudy_agent import SmartStudyAgent, StudentProfile
import storage
from concept_graph import ConceptGraph
from spaced_repetition import get_review_queue, get_full_schedule, ALGORITHM
from rl_policy import QLearningPolicy
from multi_format import load_any
from evaluation import compare


# ---- page config ----

st.set_page_config(
    page_title="SmartStudy Agent",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---- premium visual theme (CSS injection) ----

def inject_premium_theme():
    """Glass / gradient theme on top of the default Streamlit CSS."""
    st.markdown(
        """
        <style>
        /* ===== Fonts ===== */
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=Fira+Code:wght@400;500&display=swap');

        html, body, [class*="css"], .stApp, [data-testid="stSidebar"], .stMarkdown {
            font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif !important;
        }
        code, pre { font-family: 'Fira Code', monospace !important; }

        /* ===== Animated Background ===== */
        .stApp {
            background: linear-gradient(-45deg, #090B10, #131A2A, #0B1020, #181124) !important;
            background-size: 400% 400% !important;
            animation: gradientBG 15s ease infinite !important;
            color: #E2E8F0 !important;
        }
        
        @keyframes gradientBG {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }

        /* ===== Sidebar: glassmorphism ===== */
        [data-testid="stSidebar"] > div:first-child {
            background: rgba(13, 17, 28, 0.6) !important;
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border-right: 1px solid rgba(255, 255, 255, 0.05);
            box-shadow: 5px 0 30px rgba(0, 0, 0, 0.3);
        }
        [data-testid="stSidebar"] h1 {
            font-size: 28px !important;
            font-weight: 800 !important;
            background: linear-gradient(135deg, #00F0FF 0%, #5773FF 50%, #FF007A 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            letter-spacing: -0.5px;
        }

        /* ===== Hero welcome title ===== */
        .hero-title {
            font-size: 64px !important;
            font-weight: 800 !important;
            line-height: 1.1 !important;
            letter-spacing: -2px;
            background: linear-gradient(to right, #fff, #a5b4fc, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin: 0.1em 0 0.3em 0;
            animation: fadeInUp 0.8s cubic-bezier(0.16, 1, 0.3, 1);
        }
        .hero-sub {
            font-size: 20px;
            color: #94A3B8;
            max-width: 800px;
            line-height: 1.6;
            margin-bottom: 2.5rem;
            animation: fadeInUp 1s cubic-bezier(0.16, 1, 0.3, 1);
        }

        /* ===== Feature cards ===== */
        .ss-card-row {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin: 16px 0 12px 0;
        }
        @media (max-width: 1024px) { .ss-card-row { grid-template-columns: 1fr 1fr; } }
        @media (max-width: 600px) { .ss-card-row { grid-template-columns: 1fr; } }
        .ss-card {
            padding: 24px;
            border-radius: 20px;
            background: rgba(255, 255, 255, 0.03);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.08);
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            animation: fadeInUp 1.2s cubic-bezier(0.16, 1, 0.3, 1);
            position: relative;
            overflow: hidden;
        }
        .ss-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background: radial-gradient(circle at center, rgba(255,255,255,0.1) 0%, transparent 70%);
            opacity: 0;
            transition: opacity 0.4s ease;
        }
        .ss-card:hover::before { opacity: 1; }
        .ss-card:hover {
            transform: translateY(-8px) scale(1.02);
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
            border-color: rgba(129, 140, 248, 0.4);
            background: rgba(255, 255, 255, 0.05);
        }
        .ss-card .icon { font-size: 32px; margin-bottom: 12px; display: inline-block; }
        .ss-card:hover .icon { animation: bounce 1s ease infinite; }
        .ss-card .title { font-weight: 700; color: #F1F5F9; font-size: 17px; margin-bottom: 6px; }
        .ss-card .desc  { color: #94A3B8; font-size: 14px; line-height: 1.5; }

        /* ===== Metric cards ===== */
        div[data-testid="stMetric"] {
            background: rgba(30, 41, 59, 0.4);
            backdrop-filter: blur(12px);
            padding: 20px 24px;
            border-radius: 20px;
            border: 1px solid rgba(255, 255, 255, 0.05);
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        div[data-testid="stMetric"]::after {
            content: '';
            position: absolute;
            top: 0; left: -100%;
            width: 50%; height: 100%;
            background: linear-gradient(to right, transparent, rgba(255,255,255,0.05), transparent);
            transform: skewX(-20deg);
            transition: all 0.5s ease;
        }
        div[data-testid="stMetric"]:hover::after {
            left: 150%;
        }
        div[data-testid="stMetric"]:hover {
            transform: translateY(-4px);
            box-shadow: 0 12px 30px rgba(0, 0, 0, 0.3);
            border-color: rgba(99, 102, 241, 0.3);
        }
        div[data-testid="stMetricValue"] {
            font-size: 36px !important;
            font-weight: 800 !important;
            background: linear-gradient(135deg, #818CF8 0%, #C084FC 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            letter-spacing: -1px;
        }
        div[data-testid="stMetricLabel"] { color: #94A3B8 !important; font-weight: 600; font-size: 15px; text-transform: uppercase; letter-spacing: 1px; }

        /* ===== Buttons ===== */
        .stButton > button {
            background: linear-gradient(135deg, #6366F1 0%, #A855F7 100%) !important;
            color: white !important;
            border: none !important;
            border-radius: 12px !important;
            font-weight: 600 !important;
            font-size: 15px !important;
            padding: 0.6rem 1.5rem !important;
            box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3);
            transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
            position: relative;
            overflow: hidden;
            z-index: 1;
        }
        .stButton > button::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background: linear-gradient(135deg, #4F46E5 0%, #9333EA 100%);
            z-index: -1;
            transition: opacity 0.3s ease;
            opacity: 0;
        }
        .stButton > button:hover::before { opacity: 1; }
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(99, 102, 241, 0.5);
        }
        .stButton > button:active {
            transform: translateY(1px);
        }

        /* ===== Inputs & Selectboxes ===== */
        .stTextInput > div > div > input, .stSelectbox > div > div {
            background: rgba(15, 23, 42, 0.6) !important;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
            border-radius: 10px !important;
            color: #F8FAFC !important;
            transition: all 0.3s ease;
        }
        .stTextInput > div > div > input:focus, .stSelectbox > div > div:focus-within {
            border-color: #818CF8 !important;
            box-shadow: 0 0 0 2px rgba(129, 140, 248, 0.2) !important;
        }

        /* ===== Dataframes / Tables ===== */
        [data-testid="stDataFrame"] {
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid rgba(255, 255, 255, 0.05);
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
        }
        
        /* ===== Expander ===== */
        .streamlit-expanderHeader {
            background: rgba(30, 41, 59, 0.4) !important;
            border-radius: 10px !important;
            border: 1px solid rgba(255, 255, 255, 0.05) !important;
            font-weight: 600 !important;
            transition: all 0.3s ease;
        }
        .streamlit-expanderHeader:hover {
            background: rgba(30, 41, 59, 0.6) !important;
            border-color: rgba(129, 140, 248, 0.3) !important;
        }

        /* ===== Tabs ===== */
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
            background: transparent;
            padding-bottom: 5px;
        }
        .stTabs [data-baseweb="tab"] {
            background: rgba(30, 41, 59, 0.3);
            border-radius: 12px;
            border: 1px solid transparent;
            padding: 10px 20px;
            color: #94A3B8;
            transition: all 0.3s ease;
        }
        .stTabs [data-baseweb="tab"]:hover {
            background: rgba(30, 41, 59, 0.6);
            color: #F1F5F9;
        }
        .stTabs [aria-selected="true"] {
            background: rgba(99, 102, 241, 0.15) !important;
            border-color: rgba(129, 140, 248, 0.5) !important;
            color: #818CF8 !important;
        }

        /* ===== Live backend badge ===== */
        .backend-badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            border-radius: 999px;
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.3);
            font-weight: 600;
            font-size: 13px;
            color: #34D399;
            backdrop-filter: blur(5px);
            box-shadow: 0 0 15px rgba(16, 185, 129, 0.1);
        }
        .backend-badge.mock {
            background: rgba(245, 158, 11, 0.1);
            border-color: rgba(245, 158, 11, 0.3);
            color: #FBBF24;
            box-shadow: 0 0 15px rgba(245, 158, 11, 0.1);
        }
        .backend-badge .dot {
            width: 8px; height: 8px; border-radius: 50%;
            background: #10B981;
            box-shadow: 0 0 8px #10B981;
            animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        }
        .backend-badge.mock .dot { background: #F59E0B; box-shadow: 0 0 8px #F59E0B; }

        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: .5; transform: scale(1.2); }
        }
        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(20px); }
            to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes bounce {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-5px); }
        }

        /* ===== Subtle tweaks ===== */
        h1, h2, h3 { letter-spacing: -0.5px; font-weight: 700; }
        hr { border-color: rgba(255, 255, 255, 0.08) !important; margin: 2rem 0; }
        
        /* Custom scrollbar */
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: rgba(15, 23, 42, 0.5); }
        ::-webkit-scrollbar-thumb { background: rgba(99, 102, 241, 0.5); border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: rgba(99, 102, 241, 0.8); }
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_premium_theme()


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
        "use_mock": not (os.environ.get("ANTHROPIC_API_KEY")
                         or os.environ.get("SMARTSTUDY_LLM_BASE_URL")
                         or os.environ.get("HF_TOKEN")),
        "backend_label": (
            "Claude API" if os.environ.get("ANTHROPIC_API_KEY")
            else f"Custom LLM ({os.environ.get('SMARTSTUDY_LLM_MODEL', 'OpenAI-compatible')})"
            if os.environ.get("SMARTSTUDY_LLM_BASE_URL")
            else "HF Inference (Kimi-K2)" if os.environ.get("HF_TOKEN")
            else "Mock"
        ),
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
    """Flush the in-memory profile to SQLite."""
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

    # API mode indicator — premium badge
    if st.session_state.use_mock:
        st.markdown(
            '<div class="backend-badge mock"><span class="dot"></span>'
            'Mock Mode · Offline</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="backend-badge"><span class="dot"></span>'
            f'Live · {st.session_state.backend_label}</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # navigation
    page = st.radio("Navigate", [
        "🏠 Dashboard",
        "📖 Study Session",
        "🔁 Spaced Review",
        "🃏 Anki Export",
        "🧠 Concept Graph",
        "📊 Progress History",
        "👥 Peer Comparison",
        "🎯 RL Policy",
        "🧪 Baseline Evaluation",
        "📋 Pilot Study",
    ])


# ---- helpful banner if no student selected ----

if not st.session_state.current_student:
    st.markdown(
        """
        <div style="margin-top: 1rem;">
            <div style="font-size: 13px; font-weight: 700; letter-spacing: 3px;
                        color: #6FB3FF; text-transform: uppercase; margin-bottom: 10px;">
                Adaptive AI · POMDP · Reinforcement Learning
            </div>
            <div class="hero-title">SmartStudy Agent</div>
            <div class="hero-sub">
                An adaptive AI tutor that <b>learns how you learn</b>.
                Upload any lecture — the agent extracts topics, plans a path,
                generates quizzes, and adapts every session using a closed-loop
                reasoning cycle.
            </div>
        </div>
        <div class="ss-card-row">
            <div class="ss-card">
                <div class="icon">🧠</div>
                <div class="title">POMDP Belief State</div>
                <div class="desc">Persistent profile tracks every topic you've mastered or missed.</div>
            </div>
            <div class="ss-card">
                <div class="icon">🎯</div>
                <div class="title">RL-Driven Decisions</div>
                <div class="desc">Q-learning + LinUCB bandit pick the action — not the LLM.</div>
            </div>
            <div class="ss-card">
                <div class="icon">🔄</div>
                <div class="title">OPEAA Loop</div>
                <div class="desc">Observe → Plan → Act → Evaluate → Adapt. Five structured Claude calls.</div>
            </div>
            <div class="ss-card">
                <div class="icon">🚀</div>
                <div class="title">Deployed & Free</div>
                <div class="desc">Live on Hugging Face with a zero-cost Kimi-K2 backend.</div>
            </div>
        </div>
        <div style="margin-top: 1.5rem; padding: 14px 18px; border-radius: 12px;
                    background: rgba(74,144,226,0.10); border: 1px solid rgba(111,179,255,0.25);
                    color: #C8D7EF;">
            👈 <b>Get started</b> — create or select a student in the sidebar.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()


# --- PAGE: Dashboard ---

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


# --- PAGE: Study Session ---

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
                # feed the question bank (powers the Anki export page)
                storage.add_questions(st.session_state.current_student, [
                    {"topic": q.topic, "question": q.question,
                     "choices": q.choices, "correct_answer": q.correct_answer,
                     "explanation": q.explanation}
                    for q in st.session_state.questions
                ])

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


# --- PAGE: Spaced Review ---

elif page == "🔁 Spaced Review":
    st.title("🔁 Spaced Repetition Schedule")
    st.caption(f"Scheduling algorithm: **{ALGORITHM}**"
               + (" — memory-model-based scheduler (same family as modern Anki)"
                  if ALGORITHM == "FSRS" else ""))

    record = storage.load_student(st.session_state.current_student)
    queue = get_review_queue(record["quiz_history"])

    st.subheader("Due Now")
    if not queue:
        st.info("Nothing due for review yet. Take some quizzes first!")
    else:
        for item in queue:
            urgency = "🔴" if item["days_overdue"] > 3 else "🟡" if item["days_overdue"] > 0 else "🟢"
            extra = (f" · recall probability {item['retrievability']:.0%}"
                     if "retrievability" in item else "")
            st.markdown(
                f"{urgency} **{item['topic']}** — last score {item['last_score']:.0%}, "
                f"{item['days_overdue']} day(s) overdue · last seen {item['last_seen']}{extra}"
            )

    # FSRS full memory-state table
    schedule = get_full_schedule(record["quiz_history"])
    if schedule:
        st.divider()
        st.subheader("Memory State (all studied topics)")
        st.caption("FSRS models each topic's memory: stability = how long it lasts, "
                   "retrievability = recall probability right now.")
        sched_df = pd.DataFrame([{
            "Topic": r["topic"],
            "Recall %": f"{r['retrievability']:.0%}",
            "Stability (days)": r["stability"],
            "Difficulty": r["difficulty"],
            "Next Due": r["due"].astimezone().strftime("%Y-%m-%d"),
            "Last Seen": r["last_seen"],
        } for r in schedule])
        st.dataframe(sched_df, use_container_width=True, hide_index=True)


# --- PAGE: Anki Export ---

elif page == "🃏 Anki Export":
    st.title("🃏 Export to Anki")
    st.caption("Every quiz the agent generates is saved to your question bank. "
               "Export it as an .apkg deck and review it in Anki (FSRS-ready).")

    bank = storage.get_question_bank(st.session_state.current_student)

    if not bank:
        st.info("Question bank is empty — generate some quizzes in 📖 Study Session first.")
    else:
        by_topic = {}
        for q in bank:
            by_topic.setdefault(q["topic"], []).append(q)

        col1, col2 = st.columns(2)
        col1.metric("Cards in Bank", len(bank))
        col2.metric("Topics Covered", len(by_topic))

        st.divider()
        pick_topics = st.multiselect("Topics to export (default: all):",
                                     sorted(by_topic), default=sorted(by_topic))
        selected = [q for t in pick_topics for q in by_topic[t]]

        try:
            from anki_export import build_deck
            if selected and st.button("Build .apkg Deck", use_container_width=True):
                data = build_deck(st.session_state.current_student, selected)
                st.download_button(
                    f"⬇ Download SmartStudy_{st.session_state.current_student}.apkg "
                    f"({len(selected)} cards)",
                    data=data,
                    file_name=f"SmartStudy_{st.session_state.current_student}.apkg",
                    mime="application/octet-stream",
                    use_container_width=True,
                )
        except ImportError:
            st.warning("Anki export requires `pip install genanki`.")

        with st.expander("Preview question bank"):
            st.dataframe(pd.DataFrame([{
                "Topic": q["topic"], "Question": q["question"],
                "Answer": q["correct_answer"],
            } for q in bank]), use_container_width=True, hide_index=True)


# --- PAGE: Concept Graph ---

elif page == "🧠 Concept Graph":
    st.title("🧠 Concept Dependency Graph")

    # course selector for cross-course linking
    available = ConceptGraph.available_courses()
    selected_courses = st.multiselect(
        "Include courses (cross-course prerequisites):",
        available,
        default=[available[0]] if available else []
    )
    graph = ConceptGraph(courses=selected_courses)
    record = storage.load_student(st.session_state.current_student)
    mastered = set(record["topics_mastered"])

    # visualization — interactive (pyvis) with static matplotlib fallback
    weak = set(record["weak_areas"])
    interactive_ok = False
    try:
        from pyvis.network import Network

        net = Network(height="640px", width="100%", directed=True,
                      bgcolor="#0B1020", font_color="#E2E8F0")
        net.barnes_hut(gravity=-2500, central_gravity=0.25,
                       spring_length=140, damping=0.85)

        all_topics = set(graph.prereqs)
        for p, t in graph.to_edges():
            all_topics.add(p); all_topics.add(t)

        for t in sorted(all_topics):
            if t in mastered:
                color, status = "#16A34A", "mastered"
            elif t in weak:
                color, status = "#F59E0B", "weak area"
            else:
                color, status = "#64748B", "not studied"
            prereq_list = graph.get_prereqs(t)
            title = (f"{t} — {status}"
                     + (f"\nPrereqs: {', '.join(prereq_list)}" if prereq_list else ""))
            net.add_node(t, label=t, color=color, title=title,
                         shape="dot", size=18 if t in mastered else 14)

        for p, t in graph.to_edges():
            net.add_edge(p, t, color="#475569", arrows="to")

        html_str = net.generate_html(notebook=False)
        st.components.v1.html(html_str, height=660, scrolling=False)
        st.caption("🟢 mastered · 🟡 weak area · ⚪ not studied — drag nodes, "
                   "scroll to zoom, hover for prerequisites")
        interactive_ok = True
    except ImportError:
        pass

    if not interactive_ok:
        try:
            import networkx as nx
            G = nx.DiGraph()
            for prereq, topic in graph.to_edges():
                G.add_edge(prereq, topic)
            # add isolated nodes too
            for t in graph.prereqs:
                if t not in G:
                    G.add_node(t)

            fig, ax = plt.subplots(figsize=(14, 9))
            pos = nx.spring_layout(G, k=2.5, seed=42, iterations=50)
            node_colors = ["#16A34A" if n in mastered else "#94A3B8" for n in G.nodes()]
            nx.draw(G, pos, with_labels=True, node_color=node_colors,
                    node_size=2200, font_size=7, font_weight="bold",
                    edge_color="#64748B", arrows=True, arrowsize=15, ax=ax)
            ax.legend(handles=[
                plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#16A34A", markersize=12, label="Mastered"),
                plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#94A3B8", markersize=12, label="Not mastered"),
            ], loc="upper left")
            st.pyplot(fig)
        except ImportError:
            st.warning("Install `pyvis` or `networkx` for graph visualization.")
            edges_df = pd.DataFrame(graph.to_edges(), columns=["Prerequisite", "Topic"])
            st.dataframe(edges_df, use_container_width=True, hide_index=True)

    # missing prereqs
    st.divider()
    st.subheader("Missing Prerequisites")
    has_missing = False
    for topic in sorted(graph.prereqs):
        missing = graph.missing_prereqs(topic, list(mastered))
        if missing and topic not in mastered:
            st.markdown(f"**{topic}** needs: {', '.join(missing)}")
            has_missing = True
    if not has_missing:
        st.success("No missing prerequisites!")

    # ---- Graph Editor ----
    st.divider()
    st.subheader("Edit Concept Graph")

    col_add, col_remove = st.columns(2)

    with col_add:
        st.markdown("**Add a new topic or edge**")
        new_topic = st.text_input("Topic name", key="new_topic")
        new_prereq = st.text_input("Prerequisite (optional)", key="new_prereq")
        if st.button("Add", use_container_width=True):
            if new_topic.strip():
                if new_prereq.strip():
                    graph.add_edge(new_prereq.strip(), new_topic.strip())
                    st.success(f"Added: {new_prereq.strip()} → {new_topic.strip()}")
                else:
                    graph.add_topic(new_topic.strip())
                    st.success(f"Added topic: {new_topic.strip()}")
                st.rerun()

    with col_remove:
        st.markdown("**Remove an edge**")
        edges = graph.to_edges()
        if edges:
            edge_strs = [f"{p} → {t}" for p, t in edges]
            to_remove = st.selectbox("Select edge to remove", edge_strs)
            if st.button("Remove", use_container_width=True) and to_remove:
                parts = to_remove.split(" → ")
                graph.remove_edge(parts[0], parts[1])
                st.success(f"Removed: {to_remove}")
                st.rerun()
        else:
            st.caption("No edges to remove.")

    # show all edges as table
    with st.expander("All edges"):
        if graph.to_edges():
            st.dataframe(
                pd.DataFrame(graph.to_edges(), columns=["Prerequisite", "Topic"]),
                use_container_width=True, hide_index=True
            )


# --- PAGE: Progress History ---

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


# --- PAGE: Peer Comparison ---

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


# --- PAGE: RL Policy ---

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


# --- PAGE: Baseline Evaluation ---

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


# --- PAGE: Pilot Study ---

elif page == "📋 Pilot Study":
    st.title("📋 Pilot Study Dashboard")
    st.caption("Real usage data from students using the SmartStudy Agent")

    from pilot_study import collect_metrics, engagement_analysis, mastery_progression, generate_report

    metrics = collect_metrics()

    if metrics["n_students"] == 0:
        st.info("No student data yet. Have students complete study sessions to populate this dashboard.")
        st.stop()

    # key metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Students", metrics["n_students"])
    col2.metric("Total Sessions", metrics["total_sessions"])
    col3.metric("Avg Score", f"{metrics['avg_score_mean']:.0%}")
    col4.metric("Avg Topics Mastered", f"{metrics['avg_topics_mastered']:.1f}")

    st.divider()

    # engagement
    st.subheader("Engagement Analysis")
    engagement = engagement_analysis()
    ecol1, ecol2, ecol3 = st.columns(3)
    ecol1.metric("Active (2+ sessions)", engagement.get("active_students", 0))
    ecol2.metric("One-time users", engagement.get("one_time_students", 0))
    ecol3.metric("Retention Rate", f"{engagement.get('retention_rate', 0):.0%}")

    st.divider()

    # learning progression
    st.subheader("Learning Progression")
    progression = mastery_progression()
    if progression:
        prog_df = pd.DataFrame(progression)
        prog_df["improvement"] = prog_df["improvement"].apply(lambda x: f"{x:+.0%}")

        fig2, ax2 = plt.subplots(figsize=(10, 4))
        students = [p["student"] for p in progression]
        first = [p["first_half_avg"] * 100 for p in progression]
        second = [p["second_half_avg"] * 100 for p in progression]
        x = range(len(students))
        w = 0.35
        ax2.bar([i - w/2 for i in x], first, w, label="First half", color="#94A3B8")
        ax2.bar([i + w/2 for i in x], second, w, label="Second half", color="#2563EB")
        ax2.set_xticks(list(x))
        ax2.set_xticklabels(students, rotation=30, ha="right")
        ax2.set_ylabel("Avg Score (%)")
        ax2.axhline(70, color="gray", linestyle="--", alpha=0.5)
        ax2.legend()
        ax2.grid(axis="y", alpha=0.3)
        st.pyplot(fig2)

        st.dataframe(prog_df, use_container_width=True, hide_index=True)
    else:
        st.caption("Students need 2+ quizzes for progression analysis.")

    st.divider()

    # full report
    st.subheader("Full Report")
    report = generate_report()
    st.code(report, language="text")

    st.download_button(
        "Download Report (.txt)",
        data=report,
        file_name="pilot_study_report.txt",
        mime="text/plain",
    )

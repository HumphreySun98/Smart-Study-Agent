// sidepanel.js — persistent side-panel UI for SmartStudy Agent.
// Full OPEAA loop + live belief-state display (topics, avg score, Q-table).

import { callLLM, currentBackendInfo } from "./lib/llm_backends.js";
import { extractActiveTab } from "./lib/extractors.js";

const MAX_PAGE_CHARS = 16000;

// ---------- state ----------
const state = {
  backendInfo: null,
  pageText: "",
  pageTitle: "",
  pageKind: "html",
  topics: [],
  summary: "",
  selectedTopic: null,
  questions: [],
  answers: [],
  score: 0,
  feedback: "",
  qtable: null,
  prevScore: 0,
  // persistent belief state aggregated across sessions
  belief: {
    topics_seen: [],    // [{ name, lastScore, attempts }]
    total_score_sum: 0,
    total_attempts: 0,
    last_action: null,
  },
};

// ---------- view switching ----------
const views = ["nokey", "start", "observing", "topics", "quiz", "result", "error"];
function showView(name) {
  views.forEach(v => {
    document.getElementById(`view-${v}`).classList.toggle("hidden", v !== name);
  });
}

// ---------- storage helpers ----------
async function loadBackend() {
  const info = await currentBackendInfo();
  state.backendInfo = info;
  const badge = document.getElementById("backendBadge");
  const label = document.getElementById("backendLabel");
  const meta  = document.getElementById("metaBackend");
  if (info.hasKey) {
    badge.classList.add("ok");
    label.textContent = `Live · ${info.label}`;
  } else {
    badge.classList.remove("ok");
    label.textContent = "No API key";
  }
  meta.textContent = info.label;
  return info.hasKey;
}

async function loadQTable() {
  const { qtable } = await chrome.storage.local.get("qtable");
  state.qtable = qtable || {
    very_low:  { review: 0.05, reinforce: 0.05, advance: 0.01 },
    low:       { review: 0.05, reinforce: 0.08, advance: 0.02 },
    medium:    { review: 0.03, reinforce: 0.08, advance: 0.05 },
    high:      { review: 0.01, reinforce: 0.02, advance: 0.08 },
    very_high: { review: 0.00, reinforce: 0.01, advance: 0.10 },
  };
  if (!qtable) await chrome.storage.local.set({ qtable: state.qtable });
}

async function loadBelief() {
  const { belief } = await chrome.storage.local.get("belief");
  if (belief) state.belief = belief;
  renderBeliefPanel();
}

async function saveBelief() {
  await chrome.storage.local.set({ belief: state.belief });
  renderBeliefPanel();
}

async function saveQTable() { await chrome.storage.local.set({ qtable: state.qtable }); renderQTableMini(); }

// ---------- helpers ----------
function scoreToState(s) {
  if (s < 0.3) return "very_low";
  if (s < 0.5) return "low";
  if (s < 0.7) return "medium";
  if (s < 0.9) return "high";
  return "very_high";
}

function chooseAction(score) {
  const st = scoreToState(score);
  const row = state.qtable[st];
  if (Math.random() < 0.1) {
    const actions = Object.keys(row);
    return actions[Math.floor(Math.random() * actions.length)];
  }
  return Object.keys(row).reduce((a, b) => row[a] > row[b] ? a : b);
}

function updateQ(prev, action, next) {
  const alpha = 0.2, gamma = 0.8;
  const s = scoreToState(prev), sNext = scoreToState(next);
  const reward = (next - prev) * 10;
  const future = Math.max(...Object.values(state.qtable[sNext]));
  const old = state.qtable[s][action];
  state.qtable[s][action] = old + alpha * (reward + gamma * future - old);
  return saveQTable();
}

function extractJson(text) {
  if (!text || !text.trim()) throw new Error("Empty LLM response.");
  let s = text.trim()
    .replace(/^```(?:json)?\s*/i, "")
    .replace(/\s*```\s*$/, "")
    .trim();
  try { return JSON.parse(s); } catch (_) {}
  const firstBr = s.indexOf("[");
  const firstBc = s.indexOf("{");
  const [open, close] =
    firstBr !== -1 && (firstBc === -1 || firstBr < firstBc) ? ["[", "]"] : ["{", "}"];
  const start = s.indexOf(open);
  let end = s.lastIndexOf(close);
  while (end > start) {
    try { return JSON.parse(s.slice(start, end + 1)); }
    catch (_) { end = s.lastIndexOf(close, end - 1); }
  }
  throw new Error("Failed to parse JSON from response.");
}

function escapeHtml(s) {
  return String(s || "").replace(/[&<>"']/g,
    c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// ---------- belief panel rendering ----------
function renderBeliefPanel() {
  const panel = document.getElementById("beliefPanel");
  const count = state.belief.topics_seen.length;
  document.getElementById("bCount").textContent = count;
  const avg = state.belief.total_attempts > 0
    ? Math.round(100 * state.belief.total_score_sum / state.belief.total_attempts) + "%"
    : "—";
  document.getElementById("bAvg").textContent = avg;
  document.getElementById("bAction").textContent = (state.belief.last_action || "—").toUpperCase();

  panel.classList.toggle("empty", count === 0);
  const bTopics = document.getElementById("bTopics");
  bTopics.innerHTML = "";
  state.belief.topics_seen.slice(-12).forEach(t => {
    const chip = document.createElement("span");
    chip.className = "belief-chip" + (t.lastScore < 0.7 ? " weak" : "");
    chip.textContent = t.name.length > 22 ? t.name.slice(0, 22) + "…" : t.name;
    chip.title = `${t.name} · score ${Math.round(t.lastScore * 100)}% · ${t.attempts} attempt(s)`;
    bTopics.appendChild(chip);
  });
}

function renderQTableMini() {
  const host = document.getElementById("qtableMini");
  if (!host || !state.qtable) return;
  host.innerHTML = "";
  const actions = ["review", "reinforce", "advance"];
  const states  = ["very_low", "low", "medium", "high", "very_high"];

  host.appendChild(Object.assign(document.createElement("div"), { className: "hcell" }));
  actions.forEach(a => {
    const h = document.createElement("div"); h.className = "hcell"; h.textContent = a.slice(0, 3).toUpperCase();
    host.appendChild(h);
  });
  states.forEach(s => {
    const lbl = document.createElement("div"); lbl.className = "rowlabel"; lbl.textContent = s;
    host.appendChild(lbl);
    const row = state.qtable[s];
    const bestAction = Object.keys(row).reduce((a, b) => row[a] > row[b] ? a : b);
    actions.forEach(a => {
      const c = document.createElement("div");
      c.className = "cell" + (a === bestAction ? " best" : "");
      c.textContent = row[a].toFixed(2);
      host.appendChild(c);
    });
  });
}

function updateBeliefFromQuiz(topic, score, action) {
  const existing = state.belief.topics_seen.find(t => t.name === topic);
  if (existing) {
    existing.lastScore = score;
    existing.attempts += 1;
  } else {
    state.belief.topics_seen.push({ name: topic, lastScore: score, attempts: 1 });
  }
  state.belief.total_score_sum += score;
  state.belief.total_attempts += 1;
  state.belief.last_action = action;
}

// ---------- LLM wrapper ----------
async function llm(opts) { return callLLM(opts); }

// ---------- Phase 1: Observe ----------
async function observePage() {
  showView("observing");
  const statusEl = document.getElementById("observingStatus");
  try {
    const page = await extractActiveTab(msg => { statusEl.textContent = msg; });
    if (!page || !page.text || page.text.length < 200) {
      throw new Error(`Not enough content to analyze (got ${page?.text?.length || 0} chars).`);
    }
    state.pageText = page.text.slice(0, MAX_PAGE_CHARS);
    state.pageTitle = page.title;
    state.pageKind = page.kind;

    statusEl.textContent = `Extracting topics with ${state.backendInfo.label}…`;
    const example = `{
  "topics": [
    {"name": "Topic A", "description": "one-sentence description", "priority": "high"},
    {"name": "Topic B", "description": "...", "priority": "medium"}
  ],
  "summary": "one-paragraph overview"
}`;
    const text = await llm({
      system:
        "You are an expert educational content analyzer. " +
        "Extract study topics from the provided content. " +
        "Return ONLY a JSON object, no prose, no markdown fences.",
      user:
        `Source title: ${state.pageTitle}\n` +
        `Source kind: ${state.pageKind}\n\n` +
        `Content:\n${state.pageText}\n\n` +
        "Extract 4-6 key study topics. Each topic needs name, description, priority (high/medium/low). " +
        "Include a one-paragraph summary.\n\n" +
        "Return JSON with keys: topics (array), summary (string).\n\n" +
        `Example:\n${example}`,
      maxTokens: 1500,
    });
    const parsed = extractJson(text);
    state.topics = Array.isArray(parsed.topics) ? parsed.topics : [];
    state.summary = parsed.summary || "";
    renderTopics();
    showView("topics");
  } catch (e) {
    showError(e);
  }
}

// ---------- Phase 2: render topics ----------
function renderTopics() {
  document.getElementById("summary").textContent = state.summary;
  const host = document.getElementById("topicList");
  host.innerHTML = "";
  state.topics.forEach((t, i) => {
    const el = document.createElement("div");
    el.className = `topic-item priority-${(t.priority || "medium").toLowerCase()}`;
    el.innerHTML = `
      <div class="topic-name">${escapeHtml(t.name)}</div>
      <div class="topic-desc">${escapeHtml(t.description || "")}</div>
    `;
    el.addEventListener("click", () => startQuizFor(i));
    host.appendChild(el);
  });
}

// ---------- Phase 3: Act ----------
async function startQuizFor(topicIdx) {
  const topic = state.topics[topicIdx];
  state.selectedTopic = topic;
  showView("observing");
  document.getElementById("observingStatus").textContent = `Generating quiz for "${topic.name}"…`;

  const example = `[
  {
    "question": "Short question text?",
    "choices": ["A) option", "B) option", "C) option", "D) option"],
    "correct_answer": "B",
    "explanation": "Short explanation."
  }
]`;
  try {
    const text = await llm({
      system: "You are an expert quiz writer. Create concise MCQs. Return ONLY a JSON array.",
      user:
        `Topic: ${topic.name}\n` +
        `Description: ${topic.description}\n` +
        `Source context: ${state.pageText.slice(0, 4000)}\n\n` +
        "Create exactly 3 MCQs. Keep each question <25 words, choices <15 words, explanations <25 words.\n\n" +
        "Return JSON array: question (str), choices (4 strs prefixed A)-D)), correct_answer (A/B/C/D), explanation (str).\n\n" +
        `Example:\n${example}`,
      maxTokens: 3000,
    });
    state.questions = extractJson(text);
    state.answers = new Array(state.questions.length).fill(null);
    renderQuiz();
    showView("quiz");
  } catch (e) { showError(e); }
}

function renderQuiz() {
  document.getElementById("quizHeader").textContent = `🎯 Quiz · ${state.selectedTopic.name}`;
  const host = document.getElementById("quizContainer");
  host.innerHTML = "";
  state.questions.forEach((q, qi) => {
    const qEl = document.createElement("div");
    qEl.className = "quiz-q";
    qEl.innerHTML = `<div class="quiz-qtext">Q${qi + 1}. ${escapeHtml(q.question)}</div>`;
    const choicesEl = document.createElement("div");
    choicesEl.className = "quiz-choices";
    q.choices.forEach(choice => {
      const letter = choice.trim().charAt(0).toUpperCase();
      const c = document.createElement("div");
      c.className = "quiz-choice";
      c.textContent = choice;
      c.dataset.letter = letter;
      c.addEventListener("click", () => {
        [...choicesEl.children].forEach(x => x.classList.remove("selected"));
        c.classList.add("selected");
        state.answers[qi] = letter;
      });
      choicesEl.appendChild(c);
    });
    qEl.appendChild(choicesEl);
    host.appendChild(qEl);
  });
}

// ---------- Phase 4+5: Evaluate + Adapt ----------
async function submitAnswers() {
  if (state.answers.includes(null)) { alert("Please answer all questions first."); return; }
  let correct = 0; const missed = [];
  state.questions.forEach((q, i) => {
    if (state.answers[i] === String(q.correct_answer).trim().toUpperCase().charAt(0)) correct++;
    else missed.push(`Q${i + 1}: ${q.question} — correct: ${q.correct_answer}`);
  });
  state.score = correct / state.questions.length;

  showView("observing");
  document.getElementById("observingStatus").textContent = "Generating feedback…";

  let feedback = "";
  try {
    feedback = await llm({
      system: "You are an encouraging tutor. Respond in 2-3 sentences.",
      user: `A student scored ${Math.round(state.score * 100)}% on ${state.selectedTopic.name}.\n` +
            (missed.length ? `Missed:\n${missed.join("\n")}\n\n` : "Perfect score!\n\n") +
            "Write 2-3 sentences of constructive feedback.",
      maxTokens: 300,
    });
  } catch (e) {
    feedback = `You scored ${Math.round(state.score * 100)}%. Keep practicing the concepts you missed.`;
  }

  const action = chooseAction(state.score);
  await updateQ(state.prevScore, action, state.score);
  state.prevScore = state.score;

  updateBeliefFromQuiz(state.selectedTopic.name, state.score, action);
  await saveBelief();

  const reason = {
    review:    `Score was ${Math.round(state.score * 100)}% — let's go back to fundamentals.`,
    reinforce: `Score was ${Math.round(state.score * 100)}% — practice variants of the same topic.`,
    advance:   `Score was ${Math.round(state.score * 100)}% — you're ready to move on.`,
  }[action];

  document.getElementById("scoreBig").textContent   = `${Math.round(state.score * 100)}%`;
  document.getElementById("feedbackText").textContent = feedback;
  document.getElementById("adaptAction").textContent  = action.toUpperCase();
  document.getElementById("adaptReason").textContent  = reason;
  renderQTableMini();
  showView("result");
}

function showError(err) {
  document.getElementById("errorText").textContent = String(err.message || err);
  showView("error");
}

// ---------- Boot ----------
async function boot() {
  await loadQTable();
  await loadBelief();
  renderQTableMini();
  const hasKey = await loadBackend();
  showView(hasKey ? "start" : "nokey");
}

// wire events
document.getElementById("openOptions").addEventListener("click", () => chrome.runtime.openOptionsPage());
document.getElementById("footSettings").addEventListener("click", (e) => {
  e.preventDefault(); chrome.runtime.openOptionsPage();
});
document.getElementById("btnObserve").addEventListener("click", observePage);
document.getElementById("btnRestart").addEventListener("click",  () => showView("start"));
document.getElementById("btnRestart2").addEventListener("click", () => showView("start"));
document.getElementById("btnBackTopics").addEventListener("click", () => showView("topics"));
document.getElementById("btnSubmit").addEventListener("click", submitAnswers);
document.getElementById("btnNewQuiz").addEventListener("click", () => showView("topics"));
document.getElementById("btnRetry").addEventListener("click",   () => showView("start"));

// refresh backend badge when storage changes (e.g., user changes backend in options)
chrome.storage.onChanged.addListener(changes => {
  if (changes.backend || changes.anthropicKey || changes.hfKey) loadBackend();
});

boot();

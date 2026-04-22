// popup.js — SmartStudy Chrome Extension logic.
// Implements the OPEAA loop:  Observe → Plan → Act → Evaluate → Adapt.
// The agent runs client-side. The Q-table is persisted in chrome.storage.local
// so the policy learns across sessions, just like the Streamlit version.

const API_URL   = "https://api.anthropic.com/v1/messages";
const MODEL_ID  = "claude-opus-4-5";
const MAX_PAGE_CHARS = 12000;

// ---------- state ----------
const state = {
  apiKey: null,
  pageText: "",
  pageTitle: "",
  topics: [],            // [{name, description, priority}]
  summary: "",
  selectedTopic: null,
  questions: [],         // [{question, choices[], correct_answer, explanation}]
  answers: [],
  score: 0,
  feedback: "",
  qtable: null,          // {state: {action: q_value}}
  prevScore: 0,
};

// ---------- view switching ----------
const views = ["nokey", "start", "observing", "topics", "quiz", "result", "error"];
function showView(name) {
  views.forEach(v => {
    document.getElementById(`view-${v}`).classList.toggle("hidden", v !== name);
  });
}

// ---------- API key + backend badge ----------
async function loadApiKey() {
  const { anthropicKey } = await chrome.storage.local.get("anthropicKey");
  state.apiKey = anthropicKey || null;
  const badge = document.getElementById("backendBadge");
  const label = document.getElementById("backendLabel");
  if (state.apiKey) {
    badge.classList.add("ok");
    label.textContent = "Live · Claude API";
  } else {
    badge.classList.remove("ok");
    label.textContent = "No API key";
  }
  return state.apiKey;
}

async function loadQTable() {
  const { qtable } = await chrome.storage.local.get("qtable");
  if (qtable) { state.qtable = qtable; return; }
  state.qtable = {
    very_low:  { review: 0.05, reinforce: 0.05, advance: 0.01 },
    low:       { review: 0.05, reinforce: 0.08, advance: 0.02 },
    medium:    { review: 0.03, reinforce: 0.08, advance: 0.05 },
    high:      { review: 0.01, reinforce: 0.02, advance: 0.08 },
    very_high: { review: 0.00, reinforce: 0.01, advance: 0.10 },
  };
  await chrome.storage.local.set({ qtable: state.qtable });
}

async function saveQTable() {
  await chrome.storage.local.set({ qtable: state.qtable });
}

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
  // epsilon-greedy with small epsilon for demo stability
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
  try { return JSON.parse(s); } catch (_) { /* fall through */ }

  // find outermost JSON
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

// ---------- LLM call ----------
async function claude({ system, user, maxTokens = 2048 }) {
  if (!state.apiKey) throw new Error("No API key.");
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": state.apiKey,
      "anthropic-version": "2023-06-01",
      "anthropic-dangerous-direct-browser-access": "true",
    },
    body: JSON.stringify({
      model: MODEL_ID,
      max_tokens: maxTokens,
      system,
      messages: [{ role: "user", content: user }],
    }),
  });
  if (!resp.ok) {
    const err = await resp.text();
    throw new Error(`Claude API ${resp.status}: ${err.slice(0, 240)}`);
  }
  const data = await resp.json();
  const block = (data.content || []).find(b => b.type === "text");
  if (!block) throw new Error("No text block in response.");
  return block.text;
}

// ---------- Phase 1: Observe ----------
async function observePage() {
  showView("observing");
  document.getElementById("observingStatus").textContent = "Reading page content…";

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.id) throw new Error("No active tab.");

  const results = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    files: ["content.js"],
  });
  const page = results[0]?.result;
  if (!page || !page.text || page.text.length < 200) {
    throw new Error("Not enough page content to analyze (need >200 chars).");
  }
  state.pageText = page.text.slice(0, MAX_PAGE_CHARS);
  state.pageTitle = page.title;

  document.getElementById("observingStatus").textContent = "Extracting topics with Claude…";

  const system =
    "You are an expert educational content analyzer. " +
    "Extract study topics from web content. " +
    "Return ONLY a JSON object, no prose, no markdown fences.";

  const example = `{
  "topics": [
    {"name": "Topic A", "description": "one-sentence description", "priority": "high"},
    {"name": "Topic B", "description": "...", "priority": "medium"}
  ],
  "summary": "one-paragraph overview"
}`;

  const text = await claude({
    system,
    user:
      `Page title: ${state.pageTitle}\n\n` +
      `Page content:\n${state.pageText}\n\n` +
      "Extract 4-6 key study topics. For each, include a short description and " +
      "a priority ('high' / 'medium' / 'low') based on centrality to the page. " +
      "Also include a one-paragraph summary of the overall content.\n\n" +
      "Return a JSON object with exactly these keys:\n" +
      "  topics — array of objects with {name, description, priority}\n" +
      "  summary — short paragraph\n\n" +
      `Example of the required format:\n${example}`,
    maxTokens: 1500,
  });

  const parsed = extractJson(text);
  state.topics = Array.isArray(parsed.topics) ? parsed.topics : [];
  state.summary = parsed.summary || "";
  renderTopics();
  showView("topics");
}

// ---------- Phase 2: Render topics ----------
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

function escapeHtml(s) {
  return String(s || "").replace(/[&<>"']/g,
    c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// ---------- Phase 3: Act (generate quiz) ----------
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

  const text = await claude({
    system:
      "You are an expert quiz writer. Create concise MCQs. " +
      "Return ONLY a JSON array, no prose.",
    user:
      `Topic: ${topic.name}\n` +
      `Description: ${topic.description}\n` +
      `Page context: ${state.pageText.slice(0, 4000)}\n\n` +
      "Create exactly 3 multiple-choice questions. " +
      "Keep each question under 25 words, each choice under 15 words, each explanation under 25 words.\n\n" +
      "Return a JSON array where each element has:\n" +
      "  question — string\n" +
      "  choices — array of 4 strings prefixed 'A) ', 'B) ', 'C) ', 'D) '\n" +
      "  correct_answer — single letter A/B/C/D\n" +
      "  explanation — short string\n\n" +
      `Example:\n${example}`,
    maxTokens: 2500,
  });

  const parsed = extractJson(text);
  state.questions = parsed;
  state.answers = new Array(parsed.length).fill(null);
  renderQuiz();
  showView("quiz");
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

// ---------- Phase 4 + 5: Evaluate + Adapt ----------
async function submitAnswers() {
  if (state.answers.includes(null)) {
    alert("Please answer all questions first.");
    return;
  }
  // evaluate locally
  let correct = 0;
  const missed = [];
  state.questions.forEach((q, i) => {
    if (state.answers[i] === String(q.correct_answer).trim().toUpperCase().charAt(0)) {
      correct++;
    } else {
      missed.push(`Q${i + 1}: ${q.question} — correct: ${q.correct_answer}`);
    }
  });
  state.score = correct / state.questions.length;

  showView("observing");
  document.getElementById("observingStatus").textContent = "Generating feedback…";

  // short feedback from Claude
  let feedback = "";
  try {
    feedback = await claude({
      system: "You are an encouraging tutor. Respond in 2-3 sentences, no JSON.",
      user: `A student scored ${Math.round(state.score * 100)}% on ${state.selectedTopic.name}.\n` +
            (missed.length ? `Missed:\n${missed.join("\n")}\n\n` : "Perfect score!\n\n") +
            "Write 2-3 sentences of constructive, encouraging feedback.",
      maxTokens: 300,
    });
  } catch (e) {
    feedback = `You scored ${Math.round(state.score * 100)}%. Keep practicing — especially the concepts you missed.`;
  }

  // Q-learning: update table with (prev_score, chosen_action, new_score)
  const action = chooseAction(state.score);
  await updateQ(state.prevScore, action, state.score);
  state.prevScore = state.score;

  const reason = {
    review:    `Score was ${Math.round(state.score * 100)}% — let's go back to fundamentals.`,
    reinforce: `Score was ${Math.round(state.score * 100)}% — practice variants of the same topic.`,
    advance:   `Score was ${Math.round(state.score * 100)}% — you're ready to move on.`,
  }[action];

  document.getElementById("scoreBig").textContent = `${Math.round(state.score * 100)}%`;
  document.getElementById("feedbackText").textContent = feedback;
  document.getElementById("adaptAction").textContent = action.toUpperCase();
  document.getElementById("adaptReason").textContent = reason;
  showView("result");
}

// ---------- Error handling ----------
function showError(err) {
  document.getElementById("errorText").textContent = String(err.message || err);
  showView("error");
}

// ---------- Boot ----------
async function boot() {
  await loadQTable();
  const key = await loadApiKey();
  showView(key ? "start" : "nokey");
}

// wire events
document.getElementById("openOptions").addEventListener("click", () => chrome.runtime.openOptionsPage());
document.getElementById("footSettings").addEventListener("click", (e) => {
  e.preventDefault();
  chrome.runtime.openOptionsPage();
});
document.getElementById("btnObserve").addEventListener("click", async () => {
  try { await observePage(); } catch (e) { showError(e); }
});
document.getElementById("btnRestart").addEventListener("click",  () => showView("start"));
document.getElementById("btnRestart2").addEventListener("click", () => showView("start"));
document.getElementById("btnBackTopics").addEventListener("click", () => showView("topics"));
document.getElementById("btnSubmit").addEventListener("click", async () => {
  try { await submitAnswers(); } catch (e) { showError(e); }
});
document.getElementById("btnNewQuiz").addEventListener("click", () => showView("topics"));
document.getElementById("btnRetry").addEventListener("click",   () => showView("start"));

boot();

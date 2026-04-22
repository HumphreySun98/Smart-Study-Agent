// options.js — stores API key + model in chrome.storage.local.

const $ = id => document.getElementById(id);
const keyEl = $("apiKey");
const modelEl = $("model");
const statusEl = $("status");

async function load() {
  const { anthropicKey, model } = await chrome.storage.local.get(["anthropicKey", "model"]);
  if (anthropicKey) keyEl.value = anthropicKey;
  if (model) modelEl.value = model;
}

function flashStatus(msg, kind = "ok") {
  statusEl.textContent = msg;
  statusEl.className = `status ${kind}`;
  statusEl.style.display = "block";
  setTimeout(() => { statusEl.style.display = "none"; }, 2500);
}

$("save").addEventListener("click", async () => {
  const key = keyEl.value.trim();
  const model = modelEl.value.trim() || "claude-opus-4-5";
  if (!key.startsWith("sk-ant-")) {
    flashStatus("Key should start with 'sk-ant-'. Double-check it.", "warn");
    return;
  }
  await chrome.storage.local.set({ anthropicKey: key, model });
  flashStatus("Saved. Open the extension popup to start.", "ok");
});

$("toggleVis").addEventListener("click", () => {
  const is = keyEl.type === "password";
  keyEl.type = is ? "text" : "password";
  $("toggleVis").textContent = is ? "Hide" : "Show";
});

$("resetQ").addEventListener("click", async () => {
  await chrome.storage.local.remove("qtable");
  flashStatus("Q-table cleared. The agent will re-learn from scratch.", "ok");
});

load();

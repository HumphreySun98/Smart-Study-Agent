// options.js — manage backend selection + keys in chrome.storage.local.

const $ = id => document.getElementById(id);

let currentBackend = "anthropic";

function renderBackendSelection() {
  ["anthropic", "hf"].forEach(id => {
    $(`opt-${id}`).classList.toggle("selected", currentBackend === id);
    $(`fields-${id}`).classList.toggle("active", currentBackend === id);
  });
}

async function load() {
  const { backend, anthropicKey, hfKey, model } = await chrome.storage.local.get([
    "backend", "anthropicKey", "hfKey", "model",
  ]);
  currentBackend = backend || "anthropic";
  if (anthropicKey) $("anthropicKey").value = anthropicKey;
  if (hfKey) $("hfKey").value = hfKey;
  if (model) $("model").value = model;
  renderBackendSelection();
}

function flashStatus(msg, kind = "ok") {
  const el = $("status");
  el.textContent = msg;
  el.className = `status ${kind}`;
  el.style.display = "block";
  setTimeout(() => { el.style.display = "none"; }, 2800);
}

// backend picker
document.querySelectorAll(".backend-option").forEach(btn => {
  btn.addEventListener("click", () => {
    currentBackend = btn.dataset.backend;
    renderBackendSelection();
  });
});

// show/hide toggles
function wireToggle(btnId, inputId) {
  $(btnId).addEventListener("click", () => {
    const input = $(inputId);
    const is = input.type === "password";
    input.type = is ? "text" : "password";
    $(btnId).textContent = is ? "Hide" : "Show";
  });
}
wireToggle("toggleAnthropic", "anthropicKey");
wireToggle("toggleHf", "hfKey");

// save
$("save").addEventListener("click", async () => {
  const anthropicKey = $("anthropicKey").value.trim();
  const hfKey       = $("hfKey").value.trim();
  const model       = $("model").value.trim();

  // basic sanity
  if (currentBackend === "anthropic" && anthropicKey && !anthropicKey.startsWith("sk-ant-")) {
    flashStatus("Anthropic key should start with 'sk-ant-'.", "warn"); return;
  }
  if (currentBackend === "hf" && hfKey && !hfKey.startsWith("hf_")) {
    flashStatus("HF token should start with 'hf_'.", "warn"); return;
  }
  const needed = currentBackend === "anthropic" ? anthropicKey : hfKey;
  if (!needed) {
    flashStatus(`Paste your ${currentBackend === "anthropic" ? "Anthropic key" : "HF token"} first.`, "warn"); return;
  }

  await chrome.storage.local.set({
    backend: currentBackend,
    anthropicKey: anthropicKey || undefined,
    hfKey: hfKey || undefined,
    model: model || undefined,
  });
  const label = currentBackend === "anthropic" ? "Claude" : "HF Kimi-K2";
  flashStatus(`Saved. ${label} backend is active. Open the extension popup to start.`);
});

$("resetQ").addEventListener("click", async () => {
  await chrome.storage.local.remove("qtable");
  flashStatus("Q-table cleared. The agent will re-learn from scratch.");
});

load();

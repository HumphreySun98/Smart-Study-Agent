// lib/llm_backends.js
// Pluggable LLM backend layer — same interface, swappable provider.
// Used by popup.js and sidepanel.js. Called as ES module.

// -------- Anthropic Claude (direct browser call) --------

async function callAnthropic({ apiKey, model, system, user, maxTokens }) {
  const resp = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
      "anthropic-dangerous-direct-browser-access": "true",
    },
    body: JSON.stringify({
      model: model || "claude-opus-4-5",
      max_tokens: maxTokens || 2048,
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
  if (!block) throw new Error("No text block in Claude response.");
  return block.text;
}


// -------- Hugging Face Inference Router (OpenAI-compatible) --------
// Free tier w/ Kimi-K2 (or Llama-3, etc.).
// Endpoint: https://router.huggingface.co/v1/chat/completions

async function callHFRouter({ apiKey, model, system, user, maxTokens }) {
  const messages = [];
  if (system) messages.push({ role: "system", content: system });
  messages.push({ role: "user", content: user });

  let lastErr = null;
  // retry with temperature annealing — Kimi-K2 occasionally returns empty
  for (const temperature of [0.3, 0.1, 0.0]) {
    try {
      const resp = await fetch("https://router.huggingface.co/v1/chat/completions", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "authorization": `Bearer ${apiKey}`,
        },
        body: JSON.stringify({
          model: model || "moonshotai/Kimi-K2-Instruct-0905",
          messages,
          max_tokens: Math.max(maxTokens || 1500, 1500),
          temperature,
        }),
      });
      if (!resp.ok) {
        const err = await resp.text();
        lastErr = new Error(`HF Router ${resp.status}: ${err.slice(0, 240)}`);
        continue;
      }
      const data = await resp.json();
      const text = (data.choices || [])[0]?.message?.content || "";
      if (text.trim()) return text;
      lastErr = new Error("HF Router returned empty content.");
    } catch (e) {
      lastErr = e;
    }
    await new Promise(r => setTimeout(r, 500));
  }
  throw lastErr || new Error("HF Router failed after 3 retries.");
}


// -------- Unified entrypoint --------

export async function callLLM({ system, user, maxTokens = 2048 }) {
  const { backend, anthropicKey, hfKey, model } = await chrome.storage.local.get([
    "backend", "anthropicKey", "hfKey", "model",
  ]);
  const selected = backend || "anthropic";

  if (selected === "hf") {
    if (!hfKey) throw new Error("No HF token. Open Settings to add one.");
    return callHFRouter({
      apiKey: hfKey,
      model: model || "moonshotai/Kimi-K2-Instruct-0905",
      system, user, maxTokens,
    });
  }

  // default: anthropic
  if (!anthropicKey) throw new Error("No Anthropic API key. Open Settings to add one.");
  return callAnthropic({
    apiKey: anthropicKey,
    model: model || "claude-opus-4-5",
    system, user, maxTokens,
  });
}


// -------- Backend metadata (for UI labels) --------

export async function currentBackendInfo() {
  const { backend, anthropicKey, hfKey, model } = await chrome.storage.local.get([
    "backend", "anthropicKey", "hfKey", "model",
  ]);
  const selected = backend || "anthropic";
  if (selected === "hf") {
    return {
      id: "hf",
      label: "HF Kimi-K2",
      model: model || "moonshotai/Kimi-K2-Instruct-0905",
      hasKey: !!hfKey,
    };
  }
  return {
    id: "anthropic",
    label: "Claude API",
    model: model || "claude-opus-4-5",
    hasKey: !!anthropicKey,
  };
}

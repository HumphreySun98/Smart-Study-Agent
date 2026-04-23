# SmartStudy Agent — Privacy Policy

_Last updated: April 2026_

SmartStudy Agent ("the extension") is an open-source Chrome extension developed and maintained by Haofei Sun. This page describes exactly what data the extension handles.

---

## 1. What the extension collects

**The extension does not collect, transmit, or store any personal data on a server we control.**

The following information is stored **locally on your own device** via `chrome.storage.local`:

| Field | Purpose |
|-------|---------|
| `anthropicKey` (optional) | Your Anthropic API key, used only to call `api.anthropic.com` directly from your browser |
| `hfKey` (optional) | Your Hugging Face access token, used only to call `router.huggingface.co` directly from your browser |
| `backend` | Which LLM backend you selected ("anthropic" or "hf") |
| `model` | Optional model-name override |
| `qtable` | The Q-learning policy state (numeric values) updated as you use the extension |
| `belief` | Your aggregated learning state — topic names you've seen, your average score, last action taken |

These values never leave your browser except as part of the LLM requests you explicitly initiate (see §2).

---

## 2. What data is sent to third parties

When you click **Observe this page** or **Submit answers**, the extension makes HTTPS requests to the LLM provider you selected:

- **Anthropic** (`api.anthropic.com`) — receives: your API key, the visible text content of the active page (capped at ~16 KB), and any prompts the extension generates.
- **Hugging Face Router** (`router.huggingface.co`) — receives: your HF token, the same content and prompts, routed to the open-weight model you selected (e.g., Kimi-K2).
- **YouTube** (`youtube.com`) — when the active tab is a YouTube video, the extension fetches the caption track (XML transcript) from YouTube's own `timedtext` endpoint. No additional data is sent.

The extension does **not** contact any server controlled by the SmartStudy Agent developer.

Your API keys are sent **only** to the corresponding provider (Anthropic or Hugging Face).

---

## 3. What the extension does not do

- ❌ No tracking cookies
- ❌ No analytics
- ❌ No advertisements
- ❌ No data sold or shared with third parties
- ❌ No syncing across devices (data stays in `chrome.storage.local`, not `chrome.storage.sync`)
- ❌ No access to page content outside of the active tab
- ❌ No background polling — the extension only acts when you click a button

---

## 4. Page content

When you click **Observe this page**, the extension injects a content script into the active tab that reads the visible rendered text. For PDFs, it fetches the PDF bytes from the URL and parses them locally with pdf.js. For YouTube videos, it fetches the public caption track.

This content is sent to your chosen LLM provider (see §2). It is **not** retained anywhere by the extension after the API call completes.

---

## 5. Uninstalling

Uninstalling the extension via `chrome://extensions` wipes all stored data (API keys, Q-table, belief state).

---

## 6. Contact

Questions or concerns? Open an issue at
[github.com/HumphreySun98/Smart-Study-Agent](https://github.com/HumphreySun98/Smart-Study-Agent).

---

## 7. Changes to this policy

Material changes will be noted in the project's CHANGELOG and, where significant, surfaced in a new version of the extension's release notes.

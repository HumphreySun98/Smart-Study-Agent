# SmartStudy Agent — Chrome Extension

Turns any **web page**, **PDF**, or **YouTube video** into a personalized quiz with a closed-loop reasoning cycle.
Same OPEAA agent as the [web app](https://huggingface.co/spaces/HumphreySun98/smart-study-agent), delivered as a **Side Panel extension** that learns across sessions.

<p align="center">
  <img src="screenshots/popup.png" alt="SmartStudy Chrome extension popup" width="360" />
</p>

<p align="center">
  <img src="icons/icon128.png" alt="SmartStudy icon" width="64" />
</p>

---

## What it does

One click on any page → side panel opens → runs the full OPEAA loop:

1. **Observe** — smart extractor routes to the right handler:
   - 🌐 HTML pages → visible-text scrape
   - 📄 PDF URLs → fetched + parsed locally with `pdf.js`
   - ▶️ YouTube → caption-track fetch from `ytInitialPlayerResponse`
2. **Plan** — LLM extracts 4-6 study topics + priorities
3. **Act** — click any topic to generate a 3-MCQ quiz
4. **Evaluate** — score + targeted LLM feedback
5. **Adapt** — **tabular Q-learning** (not the LLM) picks the next action —
   `advance`, `reinforce`, or `review`. Q-table persists across sessions.

The **side panel stays open** as you browse, with a live **belief state** display (topics seen, avg score, last action) and a mini Q-table heatmap.

---

## Two backends — free or premium

| | Model | Cost | Setup |
|---|---|---|---|
| **Anthropic** | `claude-opus-4-5` | Pay-as-you-go | [Get key](https://console.anthropic.com/settings/keys) |
| **Hugging Face** | `Kimi-K2-Instruct-0905` | **Free** | [Get token](https://huggingface.co/settings/tokens) |

Switch any time in the extension's Settings — all local state (Q-table, belief) is preserved.

---

## Install (unpacked, < 60 seconds)

1. Clone or download this repo.
2. Open `chrome://extensions`.
3. Enable **Developer mode** (top-right).
4. Click **Load unpacked** → pick the `chrome-extension/` directory.
5. Pin the SmartStudy icon. **Clicking it opens the Side Panel.**
6. First launch opens Settings — pick a backend, paste your key, Save.

---

## Usage

- **HTML page** — any article, docs, Wikipedia page with body content
- **PDF** — open any `*.pdf` URL in Chrome and click the extension icon
- **YouTube** — open a video with captions available

Click **Observe this page** → pick a topic → answer the MCQs → see the **Agent decision** and the **learned Q-table**.

Open Settings → **Reset Q-table** to clear learned state.

---

## Architecture

```
┌────────────────────────────────────┐
│  Side Panel (sidepanel.html/.js)   │  ← persistent UI with belief-state display
└──────────────┬─────────────────────┘
               │
               ▼
┌────────────────────────────────────┐
│  extractors.js                     │
│  ├── HTML  →  content.js injection │
│  ├── PDF   →  pdf_extract.js       │
│  └── YT    →  ytInitialPlayerResp. │
└──────────────┬─────────────────────┘
               │
               ▼
┌────────────────────────────────────┐
│  llm_backends.js                   │
│  ├── callAnthropic()  (direct)     │
│  └── callHFRouter()   (OpenAI-compat)│
└──────────────┬─────────────────────┘
               │
               ▼
┌────────────────────────────────────┐
│  Q-learning policy                 │
│  state: score bucket (5)           │
│  action: review/reinforce/advance  │
│  reward: Δscore × 10               │
│  persisted in chrome.storage.local │
└────────────────────────────────────┘
```

### Permissions

| Permission | Used for |
|-----------|----------|
| `activeTab` + `scripting` | Inject content script into the active tab on click |
| `storage` | Persist API key, Q-table, belief state |
| `sidePanel` | Open the persistent side-panel UI |
| `<all_urls>` host | Required so Observe works on arbitrary pages |
| `api.anthropic.com`, `router.huggingface.co` | The only LLM endpoints we call |
| `*.youtube.com` | Fetch public caption XML for transcript extraction |

---

## Privacy

Full detail in [PRIVACY.md](PRIVACY.md).

TL;DR — **no server we control, no tracking, no analytics**. Your API key lives in `chrome.storage.local` and is sent **only** directly to Anthropic or Hugging Face. Page content is sent only to the LLM provider you selected, only when you click an action button.

Uninstalling the extension wipes all local data.

---

## Publish to the Chrome Web Store

Full guide in [WEB_STORE_SUBMISSION.md](WEB_STORE_SUBMISSION.md). Quick path:

```bash
bash package.sh         # builds dist/smartstudy-agent-v0.2.0.zip
# → upload that zip at chrome.google.com/webstore/devconsole
```

---

## Roadmap

- [x] MVP popup with the full OPEAA loop
- [x] Persistent Q-table across sessions
- [x] **Side Panel** migration with live belief-state display
- [x] **PDF viewer integration** (local `pdf.js` parsing)
- [x] **YouTube transcript** extraction
- [x] **Multi-backend**: Anthropic Claude + HF Kimi-K2 router
- [x] **Web Store deliverables**: privacy policy + submission guide + package script
- [ ] Ship to the Chrome Web Store (owner action)
- [ ] Options-page telemetry opt-in (anonymous usage stats)
- [ ] Fine-tuned per-topic Q-tables (vs. current global)

---

## Known limitations (v0.2.0)

- `file://` and `chrome://` URLs are blocked by Chrome for content scripts.
- Some PDF hosts serve with CORS restrictions — if fetch fails, open the PDF in a new tab from the source site.
- YouTube transcript fallback uses the first available track; non-English videos without English captions fall back to HTML page scrape.
- The extension calls LLM APIs directly from the browser — fine for personal use, but a production deployment should proxy through a server.

---

Part of [Smart-Study-Agent](https://github.com/HumphreySun98/Smart-Study-Agent) · MIT License

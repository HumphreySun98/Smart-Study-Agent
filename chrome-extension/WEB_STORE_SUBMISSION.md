# Chrome Web Store — Submission Guide

Everything you need to publish SmartStudy Agent to the Chrome Web Store.

---

## 0. One-time prerequisites

1. **Developer account** — pay the $5 one-time registration fee at
   [chrome.google.com/webstore/devconsole](https://chrome.google.com/webstore/devconsole).
2. **Host the privacy policy** — upload `PRIVACY.md` (rendered as HTML) to
   GitHub Pages or any public URL. A common approach is to use the raw GitHub
   link: `https://github.com/HumphreySun98/Smart-Study-Agent/blob/main/chrome-extension/PRIVACY.md`
3. **Gather screenshots** — 1280×800 (or 640×400) PNG/JPG. Minimum 1, up to 5.

---

## 1. Build the package

From repo root:

```bash
cd chrome-extension
bash package.sh
```

This produces `dist/smartstudy-agent-v0.2.0.zip` — ready to upload.

If you don't have `package.sh` yet, the one-liner is:

```bash
(cd chrome-extension && zip -r ../smartstudy-agent-v0.2.0.zip . \
    -x "screenshots/*" "dist/*" "*.md" "package.sh")
```

---

## 2. Listing fields (copy-paste ready)

### Name
```
SmartStudy Agent
```

### Summary (up to 132 chars)
```
Adaptive AI tutor — turns any page, PDF, or YouTube video into a personalized quiz with a closed-loop reasoning cycle.
```

### Detailed description

```
SmartStudy Agent is an adaptive AI tutor that turns any web page, PDF, or YouTube video into a personalized quiz.

HOW IT WORKS
Five-phase closed-loop reasoning cycle grounded in POMDP theory:
• Observe — extracts study topics from the active tab
• Plan — prioritizes topics based on your learning history
• Act — generates 3 multiple-choice questions per topic
• Evaluate — scores your answers and gives targeted feedback
• Adapt — a Q-learning policy (not the LLM) picks the next action: advance, reinforce, or review

FEATURES
• Side panel that stays open as you browse — your belief state is always visible
• Works on any web page, PDF URL, or YouTube video (auto-extracts transcripts)
• Two LLM backends: Anthropic Claude (premium quality) or Hugging Face Kimi-K2 (free)
• Client-side Q-learning — the policy learns across sessions, persisted locally
• Zero server: your API key never leaves your browser

PRIVACY-FIRST
No tracking, no analytics, no ads, no data sold. Page content is sent only to the LLM provider you selected (Anthropic or Hugging Face) and only when you click an action button.

OPEN SOURCE
MIT-licensed source at github.com/HumphreySun98/Smart-Study-Agent.

WHO IT'S FOR
Students studying lecture material, anyone learning from long-form blog posts or video tutorials, researchers reviewing papers, knowledge workers who want to test comprehension as they read.

REQUIRES
A free Hugging Face token or a paid Anthropic API key. Both are entered once in the extension's Settings tab and stored locally.
```

### Category
`Productivity`

### Language
`English`

---

## 3. Screenshots (1280×800 recommended)

Take at minimum 3 screenshots showing:

1. **Side panel on a Wikipedia article** — with topics extracted, showing belief state
2. **Side panel mid-quiz** — showing the generated MCQs
3. **Side panel with result + Q-table** — showing the learned policy and agent decision
4. *(optional)* Side panel on a YouTube video with transcript-derived topics
5. *(optional)* Settings page with backend picker (Claude vs HF)

Store the screenshots under `chrome-extension/screenshots/` and drag-drop into the dashboard.

---

## 4. Permission justifications

The dashboard asks you to justify each permission. Copy-paste these:

**`activeTab`** — Required to read the visible text of the tab the user is on when they click the extension icon. This is the entire basis of the "Observe" feature.

**`scripting`** — Required to inject the content script that extracts page text (for HTML), detects PDFs, and scrapes YouTube's `ytInitialPlayerResponse` for caption tracks.

**`storage`** — Required to persist the user's API key, the Q-learning table, and the aggregated belief state. All storage is local (`chrome.storage.local`); nothing syncs or leaves the device.

**`sidePanel`** — Required to open the main extension UI in Chrome's side panel so the belief state stays visible while the user continues browsing.

**Host permissions (`https://api.anthropic.com/*`, `https://router.huggingface.co/*`, YouTube, `<all_urls>`)** —
- `api.anthropic.com` + `router.huggingface.co`: the only servers the extension sends LLM requests to.
- `*.youtube.com`: required to fetch caption track XML from YouTube's public `timedtext` endpoint.
- `<all_urls>`: required so the Observe feature can run on whatever tab the user happens to be on. The extension reads page content only on explicit user action.

---

## 5. Privacy & data handling

Set these in the store dashboard:

- **Single purpose description**: "Adaptive AI-driven studying: extract topics from the current page and generate a personalized quiz."
- **Data usage**: Select "Not sold / used for purposes unrelated to the extension's core function".
- **Data handling certification**: Check all required boxes.
- **Privacy policy URL**: Paste your hosted `PRIVACY.md` URL.

---

## 6. After submission

- Initial review typically takes 1–3 business days.
- You'll get an email when approved.
- First-time reviewers occasionally reject for privacy-policy / permission-justification wording; just edit and resubmit.

---

## 7. Version bump checklist

Before each new upload:

- [ ] Bump `version` in `manifest.json`
- [ ] Update `CHANGELOG.md` (if present)
- [ ] Rebuild zip via `bash package.sh`
- [ ] Upload new `.zip` to the dashboard
- [ ] Click "Submit for review"

// lib/extractors.js
// Routes the active tab to the right extractor (HTML / PDF / YouTube).

import { extractPdfFromUrl } from "./pdf_extract.js";

async function getActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.id) throw new Error("No active tab.");
  return tab;
}

function isYouTube(url) {
  return /^https?:\/\/(www\.)?youtube\.com\/watch\?/.test(url);
}

function isPdfUrl(url) {
  // Heuristics: explicit .pdf extension OR Chrome-native PDF viewer.
  return /\.pdf(\?|#|$)/i.test(url) ||
         url.startsWith("chrome-extension://mhjfbmdgcfjbbpaeojofohoefgiehjai/");
}

// ---------- HTML extraction (injects content.js into the tab) ----------

async function extractHtml(tab, onStatus) {
  onStatus?.("Reading page content…");
  const results = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    files: ["content.js"],
  });
  const page = results[0]?.result;
  if (!page) throw new Error("Content script returned nothing.");
  return { ...page, kind: "html" };
}

// ---------- YouTube extraction ----------
// Scrape ytInitialPlayerResponse from the active tab, find the caption track,
// fetch the track, parse, and return its concatenated text.

async function extractYouTube(tab, onStatus) {
  onStatus?.("Detecting YouTube captions…");
  const [{ result: meta }] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: () => {
      // Find ytInitialPlayerResponse on the page
      let pr = window.ytInitialPlayerResponse;
      if (!pr) {
        // fallback: scrape from a <script> tag
        const m = document.documentElement.innerHTML.match(
          /ytInitialPlayerResponse\s*=\s*(\{.+?\})\s*;/s
        );
        if (m) {
          try { pr = JSON.parse(m[1]); } catch (_) {}
        }
      }
      if (!pr) return null;
      const tracks = pr?.captions?.playerCaptionsTracklistRenderer?.captionTracks || [];
      if (!tracks.length) return { error: "No captions available." };
      // Prefer English, else first track.
      const en = tracks.find(t => /^en/i.test(t.languageCode)) || tracks[0];
      return {
        title:  pr?.videoDetails?.title || document.title || "",
        url:    location.href,
        trackUrl: en.baseUrl,
        videoId: pr?.videoDetails?.videoId,
      };
    },
  });

  if (!meta) throw new Error("Could not parse YouTube player response.");
  if (meta.error) throw new Error(meta.error);

  onStatus?.("Fetching transcript…");
  const resp = await fetch(meta.trackUrl);
  if (!resp.ok) throw new Error(`YouTube captions fetch failed: ${resp.status}`);
  const xml = await resp.text();
  // timedtext XML: <text start="..">line</text>
  const lines = [...xml.matchAll(/<text[^>]*>([\s\S]*?)<\/text>/g)].map(m => {
    return m[1]
      .replace(/&amp;/g, "&").replace(/&quot;/g, '"')
      .replace(/&#39;/g, "'").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
      .replace(/<[^>]+>/g, "")
      .replace(/\s+/g, " ")
      .trim();
  }).filter(Boolean);
  const text = lines.join(" ").slice(0, 12000);
  return {
    kind: "youtube",
    title: meta.title,
    url: meta.url,
    text,
    length: text.length,
  };
}

// ---------- Unified entrypoint ----------

export async function extractActiveTab(onStatus) {
  const tab = await getActiveTab();
  const url = tab.url || "";

  if (isYouTube(url)) {
    try {
      return await extractYouTube(tab, onStatus);
    } catch (e) {
      // fall back to plain HTML scrape of the YouTube page
      console.warn("YouTube transcript failed, falling back to HTML:", e);
      return await extractHtml(tab, onStatus);
    }
  }

  if (isPdfUrl(url)) {
    onStatus?.("Fetching PDF…");
    return await extractPdfFromUrl(url, onStatus);
  }

  return await extractHtml(tab, onStatus);
}

// content.js — extracts the visible main content of the current page.
// Injected on-demand via chrome.scripting.executeScript from sidepanel.js.

(function () {
  function getVisibleText() {
    // Prefer semantic main/article containers if present.
    const candidates = ["article", "main", "[role='main']", "#content", "#main"];
    for (const sel of candidates) {
      const el = document.querySelector(sel);
      if (el && el.innerText && el.innerText.length > 500) {
        return el.innerText;
      }
    }
    // Fallback: grab body text but strip nav/footer/aside if possible.
    const clone = document.body.cloneNode(true);
    clone.querySelectorAll("nav, footer, aside, script, style, noscript").forEach(n => n.remove());
    return clone.innerText || "";
  }

  const raw = getVisibleText();
  const title = document.title || "";
  const url = location.href;
  const cleaned = raw
    .replace(/\n{3,}/g, "\n\n")
    .replace(/[ \t]+/g, " ")
    .trim()
    .slice(0, 12000); // cap to keep tokens reasonable

  return { title, url, text: cleaned, length: cleaned.length };
})();

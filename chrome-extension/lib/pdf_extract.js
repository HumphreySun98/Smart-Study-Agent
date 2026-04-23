// lib/pdf_extract.js
// Fetch a PDF URL, parse its text with pdf.js, return {kind, title, url, text}.

import * as pdfjs from "./pdfjs/pdf.mjs";

// Point pdf.js to the vendored worker inside our extension.
pdfjs.GlobalWorkerOptions.workerSrc = chrome.runtime.getURL("lib/pdfjs/pdf.worker.mjs");


export async function extractPdfFromUrl(url, onStatus) {
  // If the URL is chrome's built-in viewer, we can't fetch the underlying PDF
  // bytes from background — we only get there when the user opened a real PDF URL.
  // Try fetching the URL directly. If CORS blocks, surface a helpful error.
  let bytes;
  try {
    const resp = await fetch(url, { cache: "no-store" });
    if (!resp.ok) throw new Error(`PDF fetch ${resp.status}`);
    bytes = await resp.arrayBuffer();
  } catch (e) {
    throw new Error(
      "Couldn't fetch this PDF (likely CORS). Try opening the PDF in a new tab directly from its original site, or download it and open with File → Open in Chrome."
    );
  }

  onStatus?.("Parsing PDF text…");
  const pdf = await pdfjs.getDocument({ data: bytes }).promise;
  const numPages = Math.min(pdf.numPages, 40); // cap to keep tokens sane
  const chunks = [];
  for (let i = 1; i <= numPages; i++) {
    onStatus?.(`Parsing PDF page ${i}/${numPages}…`);
    const page = await pdf.getPage(i);
    const content = await page.getTextContent();
    const text = content.items.map(it => ("str" in it ? it.str : "")).join(" ");
    chunks.push(text);
  }
  const full = chunks.join("\n\n")
    .replace(/\s+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim()
    .slice(0, 16000);

  // title: try pdf metadata, fallback to URL basename
  let title = "";
  try {
    const meta = await pdf.getMetadata();
    title = meta?.info?.Title || "";
  } catch (_) {}
  if (!title) title = decodeURIComponent(url.split("/").pop() || "PDF");

  return {
    kind: "pdf",
    title,
    url,
    text: full,
    length: full.length,
    pages: pdf.numPages,
  };
}

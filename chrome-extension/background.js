// background.js — MV3 service worker.
// Minimal: open options page on first install so the user can paste an API key.

chrome.runtime.onInstalled.addListener(details => {
  if (details.reason === "install") {
    chrome.runtime.openOptionsPage();
  }
});

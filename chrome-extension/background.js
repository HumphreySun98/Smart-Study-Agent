// background.js — MV3 service worker.
// Opens the side panel when the toolbar icon is clicked, and the options
// page on first install so the user can set their API key.

chrome.runtime.onInstalled.addListener(details => {
  if (details.reason === "install") {
    chrome.runtime.openOptionsPage();
  }
});

// Make clicking the toolbar icon open the side panel (MV3 Chrome 114+).
if (chrome.sidePanel && chrome.sidePanel.setPanelBehavior) {
  chrome.sidePanel
    .setPanelBehavior({ openPanelOnActionClick: true })
    .catch(err => console.warn("sidePanel.setPanelBehavior failed:", err));
}

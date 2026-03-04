const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");
const toggleProxy = document.getElementById("toggleProxy");
const domainList = document.getElementById("domainList");
const domainCount = document.getElementById("domainCount");
const refreshBtn = document.getElementById("refreshBtn");

function updateUI(state) {
  // Toggle
  toggleProxy.checked = state.enabled;

  // Status dot and text
  if (state.status === "connected") {
    statusDot.className = "dot green";
    statusText.textContent = state.enabled ? "Active" : "Connected (off)";
  } else if (state.status === "error") {
    statusDot.className = "dot yellow";
    statusText.textContent = "Error";
  } else {
    statusDot.className = "dot red";
    statusText.textContent = "Binary not running";
  }

  // Domains
  const domains = state.domains || [];
  domainCount.textContent = domains.length;
  domainList.innerHTML = domains
    .sort()
    .map((d) => `<div class="domain-item">${d}</div>`)
    .join("");
}

// Get initial state
chrome.runtime.sendMessage({ type: "getState" }, (response) => {
  if (response) updateUI(response);
});

// Listen for status updates from background
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "status") {
    updateUI(msg);
  }
});

// Toggle handler
toggleProxy.addEventListener("change", () => {
  chrome.runtime.sendMessage(
    { type: "toggle", enabled: toggleProxy.checked },
    (response) => {
      if (response) {
        chrome.runtime.sendMessage({ type: "getState" }, (state) => {
          if (state) updateUI(state);
        });
      }
    }
  );
});

// Refresh button
refreshBtn.addEventListener("click", () => {
  refreshBtn.textContent = "...";
  chrome.runtime.sendMessage({ type: "refresh" }, (response) => {
    refreshBtn.textContent = "Refresh";
    if (response) updateUI(response);
  });
});

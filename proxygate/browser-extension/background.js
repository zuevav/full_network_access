// ProxyGate Connect — Chrome Extension Background Service Worker

const PROXY_HOST = "127.0.0.1";
const PROXY_PORT = 8800;
const STATUS_URL = `http://${PROXY_HOST}:${PROXY_PORT}/__proxygate_status`;
const CHECK_INTERVAL_MS = 30000; // 30 seconds

// State
let isEnabled = false;
let domains = [];
let proxyStatus = "disconnected";

// Load saved state
chrome.storage.local.get(["enabled", "domains"], (result) => {
  isEnabled = result.enabled || false;
  domains = result.domains || [];
  if (isEnabled) {
    applyProxy();
  }
});

// Generate PAC script for domain-based routing
function generatePAC(domainList) {
  const conditions = domainList
    .map((d) => {
      return `if (dnsDomainIs(host, "${d}") || dnsDomainIs(host, ".${d}")) return proxy;`;
    })
    .join("\n    ");

  return `function FindProxyForURL(url, host) {
    var proxy = "PROXY ${PROXY_HOST}:${PROXY_PORT}";
    ${conditions}
    return "DIRECT";
  }`;
}

// Apply proxy settings
function applyProxy() {
  if (!isEnabled || domains.length === 0) {
    chrome.proxy.settings.clear({ scope: "regular" });
    return;
  }

  const pac = generatePAC(domains);
  chrome.proxy.settings.set(
    {
      value: {
        mode: "pac_script",
        pacScript: { data: pac },
      },
      scope: "regular",
    },
    () => {
      if (chrome.runtime.lastError) {
        console.error("Failed to set proxy:", chrome.runtime.lastError);
      }
    }
  );
}

// Check proxygate-connect binary status
async function checkStatus() {
  try {
    const resp = await fetch(STATUS_URL, {
      signal: AbortSignal.timeout(5000),
    });
    if (resp.ok) {
      const data = await resp.json();
      proxyStatus = "connected";
      if (data.domains && data.domains.length > 0) {
        domains = data.domains;
        chrome.storage.local.set({ domains });
        if (isEnabled) {
          applyProxy();
        }
      }
    } else {
      proxyStatus = "error";
    }
  } catch {
    proxyStatus = "disconnected";
  }

  // Broadcast status to popup if open
  chrome.runtime.sendMessage({
    type: "status",
    enabled: isEnabled,
    status: proxyStatus,
    domains: domains,
  }).catch(() => {}); // Ignore if popup is closed
}

// Periodic status check
chrome.alarms.create("checkStatus", { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "checkStatus") {
    checkStatus();
  }
});

// Initial check
checkStatus();

// Message handler
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "toggle") {
    isEnabled = msg.enabled;
    chrome.storage.local.set({ enabled: isEnabled });
    if (isEnabled) {
      applyProxy();
    } else {
      chrome.proxy.settings.clear({ scope: "regular" });
    }
    sendResponse({ enabled: isEnabled });
  } else if (msg.type === "getState") {
    sendResponse({
      enabled: isEnabled,
      status: proxyStatus,
      domains: domains,
    });
  } else if (msg.type === "refresh") {
    checkStatus().then(() => {
      sendResponse({
        enabled: isEnabled,
        status: proxyStatus,
        domains: domains,
      });
    });
    return true; // async response
  }
});

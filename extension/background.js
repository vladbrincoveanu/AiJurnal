const MENU_ID = "aijournal-context-save";

const DEFAULTS = {
  apiBase: "",
  apiKey: "",
  sourceType: "web",
  sourceApp: "browser-extension",
};

function normalizeBase(raw) {
  if (!raw) return "";
  const trimmed = raw.replace(/\/+$/, "");
  if (trimmed.endsWith("/api")) {
    return trimmed;
  }
  return `${trimmed}/api`;
}

function notify(tabId, message) {
  if (!tabId) {
    return;
  }
  chrome.tabs.sendMessage(
    tabId,
    { type: "AIJOURNAL_NOTIFY", payload: message },
    () => chrome.runtime.lastError && console.debug(chrome.runtime.lastError),
  );
}

function getConfig() {
  return new Promise((resolve) => chrome.storage.sync.get(DEFAULTS, resolve));
}

function requestPageDetails(tabId) {
  return new Promise((resolve, reject) => {
    chrome.tabs.sendMessage(
      tabId,
      { type: "AIJOURNAL_REQUEST_SELECTION" },
      (response) => {
        if (chrome.runtime.lastError) {
          reject(chrome.runtime.lastError);
          return;
        }
        resolve(response?.payload || null);
      },
    );
  });
}

async function handleContextClick(info, tab) {
  if (info.menuItemId !== MENU_ID || !tab?.id) {
    return;
  }
  const config = await getConfig();
  if (!config.apiBase || !config.apiKey) {
    notify(tab.id, "Set API base + key in the popup first.");
    return;
  }

  let pageDetails;
  try {
    pageDetails = await requestPageDetails(tab.id);
  } catch (err) {
    console.error("AIJournal: unable to capture tab", err);
    notify(tab.id, "Unable to read this tab. Refresh and try again.");
    return;
  }

  if (!pageDetails) {
    notify(tab.id, "No page details captured.");
    return;
  }

  const base = normalizeBase(config.apiBase);
  const endpoint = `${base}/ingest`;
  const contentCandidate =
    info.selectionText ||
    pageDetails.selection ||
    pageDetails.textContent ||
    "";

  const body = {
    source_type: config.sourceType || "web",
    source_app: config.sourceApp || "browser-extension",
    title: pageDetails.title || tab.title || "",
    url_or_path: pageDetails.url || tab.url || "",
    content: contentCandidate,
    metadata: {
      captured_at: new Date().toISOString(),
      user_agent: navigator.userAgent,
      meta_description: pageDetails.metaDescription || "",
      html_snapshot: pageDetails.html || "",
    },
  };

  try {
    const resp = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${config.apiKey}`,
        "X-API-Key": config.apiKey,
      },
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(`HTTP ${resp.status}: ${text}`);
    }
    notify(tab.id, "Saved to AIJournal ✅");
  } catch (error) {
    console.error("AIJournal save failed", error);
    notify(tab.id, "Save failed. See console for details.");
  }
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: MENU_ID,
    title: "Save to AIJournal",
    contexts: ["page", "selection"],
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  handleContextClick(info, tab);
});

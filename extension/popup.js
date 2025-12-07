const apiBaseInput = document.getElementById("apiBase");
const apiKeyInput = document.getElementById("apiKey");
const titleInput = document.getElementById("title");
const urlInput = document.getElementById("url");
const contentInput = document.getElementById("content");
const sourceTypeInput = document.getElementById("sourceType");
const sourceAppInput = document.getElementById("sourceApp");
const statusEl = document.getElementById("status");
const saveConfigBtn = document.getElementById("saveConfig");
const saveMemoryBtn = document.getElementById("saveMemory");

let cachedTab = null;
let cachedMeta = null;

async function loadConfig() {
  const stored = await chrome.storage.sync.get({
    apiBase: "",
    apiKey: "",
    sourceType: "web",
    sourceApp: "browser-extension",
  });
  apiBaseInput.value = stored.apiBase;
  apiKeyInput.value = stored.apiKey;
  sourceTypeInput.value = stored.sourceType;
  sourceAppInput.value = stored.sourceApp;
}

async function saveConfig() {
  await chrome.storage.sync.set({
    apiBase: apiBaseInput.value.trim(),
    apiKey: apiKeyInput.value.trim(),
    sourceType: sourceTypeInput.value,
    sourceApp: sourceAppInput.value.trim() || "browser-extension",
  });
  setStatus("Config saved ✅");
}

function setStatus(text, isError = false) {
  statusEl.textContent = text;
  statusEl.style.color = isError ? "#f87171" : "#38bdf8";
}

async function getActiveTab() {
  const [tab] = await chrome.tabs.query({
    active: true,
    currentWindow: true,
  });
  return tab;
}

async function hydrateFromTab() {
  try {
    const tab = await getActiveTab();
    if (!tab?.id) return;
    cachedTab = tab;
    const response = await chrome.tabs.sendMessage(tab.id, {
      type: "AIJOURNAL_REQUEST_SELECTION",
    });
    if (response?.payload) {
      const { title, url, selection, metaDescription } = response.payload;
      cachedMeta = response.payload;
      titleInput.value = title || "";
      urlInput.value = url || "";
      contentInput.value = selection || metaDescription || "";
    }
  } catch (err) {
    console.warn("Failed to hydrate from tab", err);
    setStatus("Unable to read tab content (did you refresh?)", true);
  }
}

async function saveMemory() {
  const apiBase = apiBaseInput.value.trim();
  const apiKey = apiKeyInput.value.trim();
  if (!apiBase || !apiKey) {
    setStatus("API base + key required", true);
    return;
  }

  saveMemoryBtn.disabled = true;
  setStatus("Saving…");

  const payload = {
    source_type: sourceTypeInput.value || "web",
    source_app: sourceAppInput.value.trim() || "browser-extension",
    title: titleInput.value.trim() || undefined,
    url_or_path: urlInput.value.trim() || undefined,
    content: contentInput.value,
    metadata: {
      captured_at: new Date().toISOString(),
      user_agent: navigator.userAgent,
      tab_favicon: cachedTab?.favIconUrl || null,
      meta_description: cachedMeta?.metaDescription || null,
    },
  };

  try {
    const res = await fetch(new URL("/ingest", apiBase).toString(), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
        "X-API-Key": apiKey,
      },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    setStatus("Saved! 🎉");
    contentInput.value = "";
  } catch (err) {
    console.error(err);
    setStatus("Failed to save. See console.", true);
  } finally {
    saveMemoryBtn.disabled = false;
  }
}

saveConfigBtn.addEventListener("click", () => {
  saveConfig();
});

saveMemoryBtn.addEventListener("click", () => {
  saveMemory();
});

document.addEventListener("DOMContentLoaded", async () => {
  await loadConfig();
  hydrateFromTab();
});

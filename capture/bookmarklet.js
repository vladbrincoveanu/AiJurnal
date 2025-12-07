/**
 * Replace API_BASE + API_KEY, then minify (or wrap with `javascript:(function(){ ... })();`)
 * and save as a bookmark URL in your browser.
 */
const API_BASE = "https://your-api-host";
const API_KEY = "change-me";

(function () {
  const apiBase = API_BASE.replace(/\/+$/, "");
  const endpoint = `${apiBase}/api/ingest`;
  const selection = window.getSelection().toString();
  const body = {
    source_type: "web",
    source_app: "bookmarklet",
    title: document.title,
    url_or_path: location.href,
    content: selection,
    metadata: {
      captured_at: new Date().toISOString(),
      user_agent: navigator.userAgent,
    },
  };

  fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${API_KEY}`,
      "X-API-Key": API_KEY,
    },
    body: JSON.stringify(body),
  })
    .then((res) => {
      if (res.ok) {
        alert("🧠 Saved to AIJournal");
      } else {
        alert("❌ Failed to save (check console)");
      }
    })
    .catch((err) => {
      console.error(err);
      alert("❌ Network error");
    });
})();

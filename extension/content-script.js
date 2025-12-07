(() => {
  const MAX_HTML = 200_000;
  const MAX_TEXT = 10_000;

  function collectPage() {
    const selection = window.getSelection()?.toString() || "";
    const html = document.documentElement?.outerHTML || "";
    const bodyText = document.body?.innerText || "";
    return {
      type: "AIJOURNAL_SELECTION",
      payload: {
        title: document.title,
        url: window.location.href,
        selection,
        metaDescription:
          document
            .querySelector('meta[name="description"]')
            ?.getAttribute("content") || "",
        html: html.slice(0, MAX_HTML),
        textContent: bodyText.slice(0, MAX_TEXT),
      },
    };
  }

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message?.type === "AIJOURNAL_REQUEST_SELECTION") {
      sendResponse(collectPage());
      return true;
    }
    if (message?.type === "AIJOURNAL_NOTIFY" && typeof message.payload === "string") {
      alert(message.payload);
    }
    return false;
  });
})();

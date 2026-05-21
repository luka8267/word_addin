(function () {
  const readyPill = document.getElementById("ready-pill");
  const hostName = document.getElementById("host-name");
  const platformName = document.getElementById("platform-name");
  const originName = document.getElementById("origin-name");
  const statusText = document.getElementById("status-text");
  const errorLog = document.getElementById("error-log");

  function setReady(ready) {
    readyPill.textContent = ready ? "Ready" : "Loading";
    readyPill.classList.toggle("ready", ready);
  }

  function setError(message) {
    errorLog.textContent = message || "none";
  }

  originName.textContent = globalThis.location.origin;

  globalThis.addEventListener("error", function (event) {
    setError(event.message || "Unhandled error");
  });

  globalThis.addEventListener("unhandledrejection", function (event) {
    const reason = event.reason && event.reason.message ? event.reason.message : String(event.reason || "Promise rejected");
    setError(reason);
  });

  Office.onReady(function (info) {
    hostName.textContent = info.host || "unknown";
    platformName.textContent = info.platform || "unknown";
    statusText.textContent =
      info.host === Office.HostType.Word
        ? "Word で task pane が開いています。"
        : "Office.onReady は成功しましたが、Word ホストではありません。";
    setReady(true);
    setError("");
  });
})();

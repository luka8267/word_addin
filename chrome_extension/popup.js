const DEFAULT_API_BASE = "https://word-addin-sooty.vercel.app";
const DEFAULT_APP_URL = "https://bunken-h56cct98ayvusf55qxwewt.streamlit.app";
const LATEST_MANIFEST_URL = "https://raw.githubusercontent.com/luka8267/word_addin/main/chrome_extension/manifest.json";
const { DOI_RE, normalizeDoi, unique, isLikelyPaperPayload, isBlockedOrErrorPageTitle, extractFromPage, cleanMetadataText } = typeof module !== "undefined" && module.exports
  ? require("./extractor.js") : globalThis.bunkenPageMetadata;

const $ = (id) => document.getElementById(id);
let currentPayload = null;
let lastPdfCandidate = "";

function absolutizeUrl(baseUrl, candidateUrl) {
  const value = String(candidateUrl || "").trim();
  if (!value) return "";
  try {
    return new URL(value, baseUrl || undefined).href;
  } catch (_error) {
    return value;
  }
}

function buildDerivedPdfCandidates(value, url, doi) {
  const candidates = Array.isArray(value.pdfCandidates)
    ? value.pdfCandidates.map((candidate) => absolutizeUrl(url, candidate))
    : [];
  const parsedUrl = (() => {
    try { return new URL(url); } catch (_error) { return null; }
  })();
  const normalizedDoi = normalizeDoi(doi || value.doi || url);
  if (parsedUrl?.hostname === "pubs.acs.org" && DOI_RE.test(normalizedDoi)) {
    candidates.unshift(`https://pubs.acs.org/doi/pdf/${normalizedDoi}`);
    candidates.unshift(`https://pubs.acs.org/doi/pdfplus/${normalizedDoi}`);
  }
  return unique(candidates);
}

function normalizePayload(payload, tab) {
  const value = payload && typeof payload === "object" ? payload : {};
  const title = String(value.title || tab?.title || "").trim();
  const url = String(value.url || tab?.url || "").trim();
  const metadata = value.metadata && typeof value.metadata === "object" ? value.metadata : {};
  return {
    url,
    title,
    authors: Array.isArray(value.authors) ? value.authors.map(cleanMetadataText).filter(Boolean) : [],
    journal: cleanMetadataText(value.journal),
    year: cleanMetadataText(value.year),
    doi: normalizeDoi(value.doi || ""),
    volume: cleanMetadataText(value.volume) || cleanMetadataText(metadata.volume),
    issue: cleanMetadataText(value.issue) || cleanMetadataText(metadata.issue),
    pages: cleanMetadataText(value.pages) || cleanMetadataText(metadata.pages) || cleanMetadataText(metadata.citation_article_number),
    publisher: cleanMetadataText(value.publisher) || cleanMetadataText(metadata.publisher),
    abstract: String(value.abstract || "").trim(),
    pdfCandidates: buildDerivedPdfCandidates(value, url, value.doi),
    isLikelyPaper: isLikelyPaperPayload({ ...value, url, metadata }),
    metadata,
  };
}

function compareVersions(left, right) {
  const leftParts = String(left || "0").split(".").map((part) => Number.parseInt(part, 10) || 0);
  const rightParts = String(right || "0").split(".").map((part) => Number.parseInt(part, 10) || 0);
  const length = Math.max(leftParts.length, rightParts.length);
  for (let index = 0; index < length; index += 1) {
    const diff = (leftParts[index] || 0) - (rightParts[index] || 0);
    if (diff !== 0) return diff;
  }
  return 0;
}

function shouldRefreshAuth(response, result) {
  if (response?.status === 401) return true;
  const errorText = String(result?.error || result?.message || "").toLowerCase();
  return response?.status === 403 && /bad_jwt|invalid jwt|token is expired|jwt expired/.test(errorText);
}

async function checkForUpdate() {
  const currentVersion = chrome.runtime.getManifest().version;
  try {
    const response = await fetch(`${LATEST_MANIFEST_URL}?t=${Date.now()}`, { cache: "no-store" });
    const latest = await response.json();
    const latestVersion = latest?.version || "";
    if (latestVersion && compareVersions(latestVersion, currentVersion) > 0) {
      $("updateNotice").hidden = false;
      $("updateText").textContent = `最新版があります。bunkenアプリから再ダウンロードしてください。現在: ${currentVersion} / 最新: ${latestVersion}`;
    }
  } catch (_error) {
    // Update checks are best-effort; saving papers should keep working offline.
  }
}

function renderVersionLine() {
  const version = chrome.runtime.getManifest().version;
  $("versionLine").textContent = version ? `v${version}` : "";
}

function setAuthenticated(isAuthenticated) {
  $("authPanel").hidden = isAuthenticated;
  $("importPanel").hidden = !isAuthenticated;
  $("status").textContent = isAuthenticated ? "ログイン済み" : "未接続";
}

async function getActiveTabPayload() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) {
    throw new Error("No active tab found.");
  }
  try {
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["extractor.js"] });
    const injection = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => globalThis.bunkenPageMetadata.extractFromPage(),
    });
    return normalizePayload(injection?.[0]?.result, tab);
  } catch (error) {
    throw new Error("ページ情報を読み取れませんでした。論文ページと拡張機能を再読み込みしてお試しください。");
  }
}

function render(payload) {
  currentPayload = normalizePayload(payload);
  $("preview").hidden = false;
  $("title").textContent = currentPayload.title || "タイトルを取得できませんでした";
  $("meta").textContent = [currentPayload.authors.join(", "), currentPayload.journal, currentPayload.year].filter(Boolean).join(" / ");
  $("doi").textContent = currentPayload.doi ? `DOI: ${currentPayload.doi}` : "DOI: 未取得";
  lastPdfCandidate = currentPayload.pdfCandidates[0] || "";
  $("openPdf").disabled = !lastPdfCandidate;
  $("pdfCandidate").replaceChildren(...currentPayload.pdfCandidates.map((candidate) => {
    const option = document.createElement("option");
    option.value = candidate;
    option.textContent = candidate;
    return option;
  }));
  $("pdfSelectWrap").hidden = currentPayload.pdfCandidates.length === 0;
  $("pdf").textContent = lastPdfCandidate
    ? `PDF候補: ${currentPayload.pdfCandidates.length}件`
    : `PDF候補: ${currentPayload.pdfCandidates.length}件`;
}

async function loadSettings() {
  const values = await chrome.storage.sync.get(["accessToken", "refreshToken", "email"]);
  $("email").value = values.email || "";
  const isAuthenticated = Boolean(values.accessToken || values.refreshToken);
  setAuthenticated(isAuthenticated);
  return isAuthenticated;
}

async function saveSettings() {
  await chrome.storage.sync.set({
    email: $("email").value.trim(),
  });
}

async function refreshSession() {
  const values = await chrome.storage.sync.get(["refreshToken"]);
  const apiBase = DEFAULT_API_BASE;
  const refreshToken = values.refreshToken || "";
  if (!refreshToken) return "";
  const response = await fetch(`${apiBase}/api/addin/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refreshToken }),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok || !result.accessToken) return "";
  await chrome.storage.sync.set({
    accessToken: result.accessToken,
    refreshToken: result.refreshToken || refreshToken,
    email: result.email || $("email").value.trim(),
  });
  setAuthenticated(true);
  return result.accessToken;
}

async function getAccessToken() {
  const values = await chrome.storage.sync.get(["accessToken"]);
  let token = values.accessToken || "";
  if (token) return token;
  token = await refreshSession();
  return token;
}

async function openPdfCandidate() {
  const selectedCandidate = $("pdfCandidate")?.value || "";
  if (selectedCandidate) lastPdfCandidate = selectedCandidate;
  if (!lastPdfCandidate && currentPayload?.pdfCandidates?.length) {
    lastPdfCandidate = currentPayload.pdfCandidates[0];
  }
  if (!lastPdfCandidate) {
    $("message").textContent = "このページではPDF候補を取得できませんでした。";
    return;
  }
  await chrome.tabs.create({ url: lastPdfCandidate });
}

async function openApp() {
  await saveSettings();
  await chrome.tabs.create({ url: DEFAULT_APP_URL });
}

async function logout() {
  $("password").value = "";
  await chrome.storage.sync.remove(["accessToken", "refreshToken"]);
  currentPayload = null;
  $("preview").hidden = true;
  $("openPdf").disabled = true;
  setAuthenticated(false);
  $("message").textContent = "ログアウトしました。次回保存時はもう一度ログインしてください。";
}

async function login() {
  await saveSettings();
  const apiBase = DEFAULT_API_BASE;
  const email = $("email").value.trim();
  const password = $("password").value;
  if (!email || !password) {
    $("message").textContent = "メールとパスワードを入力してください。";
    return;
  }
  $("message").textContent = "ログインしています...";
  const response = await fetch(`${apiBase}/api/addin/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok || !result.accessToken) {
    $("message").textContent = `ログインに失敗しました: ${result.error || response.status}`;
    return;
  }
  $("password").value = "";
  await chrome.storage.sync.set({
    accessToken: result.accessToken,
    refreshToken: result.refreshToken || "",
    email,
  });
  setAuthenticated(true);
  $("message").textContent = "ログインしました。この文献を保存できます。";
  await extract();
}

async function extract() {
  $("message").textContent = "このページから文献情報を取得しています...";
  const payload = await getActiveTabPayload();
  render(payload);
  if (!currentPayload.isLikelyPaper) {
    $("message").textContent = "このページは論文ページとして判定できませんでした。DOIや論文メタデータがあるページで保存してください。";
    return false;
  }
  if (!currentPayload.title && !currentPayload.doi) {
    $("message").textContent = "タイトルやDOIを取得できませんでした。論文ページを開いてから更新してください。";
    return false;
  }
  $("message").textContent = "文献情報を取得しました。内容を確認して保存してください。";
  return true;
}

async function save(retried = false) {
  await saveSettings();
  if (!currentPayload) {
    const extracted = await extract();
    if (!extracted) return;
  }
  if (!currentPayload.title && !currentPayload.doi) {
    $("message").textContent = "タイトルやDOIがないため保存できません。論文ページを開いてから更新してください。";
    return;
  }
  if (!currentPayload.isLikelyPaper) {
    $("message").textContent = "このページは論文ページとして判定できないため保存しません。DOIや論文メタデータがあるページで保存してください。";
    return;
  }
  const apiBase = DEFAULT_API_BASE;
  const token = await getAccessToken();
  if (!token) {
    $("message").textContent = "一度ログインしてください。以後は自動でログイン状態を更新します。";
    setAuthenticated(false);
    return;
  }
  $("message").textContent = "bunken に保存しています...";
  const response = await fetch(`${apiBase}/api/addin/extension/save`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(currentPayload),
  });
  let result = await response.json().catch(() => ({}));
  if (shouldRefreshAuth(response, result) && !retried) {
    if (await refreshSession()) return save(true);
    await chrome.storage.sync.remove(["accessToken", "refreshToken"]);
    setAuthenticated(false);
    $("message").textContent = "ログインの有効期限が切れました。もう一度ログインしてください。";
    return;
  }
  if (!response.ok) {
    $("message").textContent = `保存に失敗しました: ${result.error || response.status}`;
    return;
  }
  const lines = [result.duplicate ? "すでに bunken に登録されています。" : "bunken に保存しました。"];
  if (Array.isArray(result.missingMetadata) && result.missingMetadata.length) {
    lines.push(`メタデータ補完待ち: ${result.missingMetadata.join(" / ")}`);
  }
  if (result.pdf?.saved) lines.push(`PDFも保存しました: ${result.pdf.storagePath}`);
  else if (result.pdfCandidates?.length) {
    lastPdfCandidate = result.pdfCandidates[0];
    render({ ...currentPayload, pdfCandidates: result.pdfCandidates });
    $("openPdf").disabled = false;
    lines.push(`PDF候補: ${result.pdfCandidates[0]}`);
    lines.push("PDFを直接保存できない場合は、PDF候補を開いてダウンロードし、bunken の文献詳細から手動でアップロードしてください。");
  }
  $("message").textContent = lines.join("\n");
}

function bootPopup() {
  renderVersionLine();
  $("extract").addEventListener("click", () => extract().catch((error) => { $("message").textContent = String(error); }));
  $("authPanel").addEventListener("submit", (event) => {
    event.preventDefault();
    login().catch((error) => { $("message").textContent = String(error); });
  });
  $("logout").addEventListener("click", () => logout().catch((error) => { $("message").textContent = String(error); }));
  $("save").addEventListener("click", () => save().catch((error) => { $("message").textContent = String(error); }));
  $("openPdf").addEventListener("click", () => openPdfCandidate().catch((error) => { $("message").textContent = String(error); }));
  $("openApp").addEventListener("click", () => openApp().catch((error) => { $("message").textContent = String(error); }));
  $("openUpdateApp").addEventListener("click", () => openApp().catch((error) => { $("message").textContent = String(error); }));

  checkForUpdate();
  loadSettings()
    .then((isAuthenticated) => {
      if (isAuthenticated) return extract();
      $("message").textContent = "";
      return null;
    })
    .catch((error) => { $("message").textContent = String(error); });
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    buildDerivedPdfCandidates,
    compareVersions,
    extractFromPage,
    getActiveTabPayload,
    normalizeDoi,
    normalizePayload,
    renderVersionLine,
    setAuthenticated,
    isBlockedOrErrorPageTitle,
    isLikelyPaperPayload,
    shouldRefreshAuth,
  };
} else {
  bootPopup();
}


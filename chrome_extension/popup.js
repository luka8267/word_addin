const DEFAULT_API_BASE = "https://word-addin-sooty.vercel.app";
const DEFAULT_APP_URL = "https://bunken-h56cct98ayvusf55qxwewt.streamlit.app";
const LATEST_MANIFEST_URL = "https://raw.githubusercontent.com/luka8267/word_addin/main/chrome_extension/manifest.json";
const DOI_RE = /10\.\d{4,9}\/[-._;()/:A-Z0-9]+/i;

const $ = (id) => document.getElementById(id);
let currentPayload = null;
let lastPdfCandidate = "";

function buildDerivedPdfCandidates(value, url, doi) {
  const candidates = Array.isArray(value.pdfCandidates) ? [...value.pdfCandidates] : [];
  const parsedUrl = (() => {
    try { return new URL(url); } catch (_error) { return null; }
  })();
  const normalizedDoi = normalizeDoi(doi || value.doi || url);
  if (parsedUrl?.hostname === "pubs.acs.org" && normalizedDoi) {
    candidates.unshift(`https://pubs.acs.org/doi/pdf/${normalizedDoi}`);
    candidates.unshift(`https://pubs.acs.org/doi/pdfplus/${normalizedDoi}`);
  }
  return unique(candidates);
}

function normalizePayload(payload, tab) {
  const value = payload && typeof payload === "object" ? payload : {};
  const title = String(value.title || tab?.title || "").trim();
  const url = String(value.url || tab?.url || "").trim();
  return {
    url,
    title,
    authors: Array.isArray(value.authors) ? value.authors : [],
    journal: String(value.journal || "").trim(),
    year: String(value.year || "").trim(),
    doi: normalizeDoi(value.doi || ""),
    abstract: String(value.abstract || "").trim(),
    pdfCandidates: buildDerivedPdfCandidates(value, url, value.doi),
    metadata: value.metadata && typeof value.metadata === "object" ? value.metadata : {},
  };
}

function normalizeDoi(value) {
  const text = String(value || "")
    .replace(/^doi:\s*/i, "")
    .replace(/^https?:\/\/(dx\.)?doi\.org\//i, "")
    .trim();
  const match = text.match(DOI_RE);
  return match ? match[0].replace(/[.,;]+$/, "") : text.replace(/[.,;]+$/, "");
}

function unique(values) {
  return [...new Set(values.filter(Boolean).map((value) => String(value).trim()).filter(Boolean))];
}

function asArray(value) {
  return Array.isArray(value) ? value : value ? [value] : [];
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

function textFromJsonLd(value) {
  if (!value) return "";
  if (typeof value === "string") return value;
  if (typeof value === "object") return value.name || value.headline || value.title || value["@id"] || value.url || "";
  return String(value || "");
}

function extractJsonLdObjects() {
  const roots = [];
  for (const script of document.querySelectorAll('script[type="application/ld+json"]')) {
    try {
      const parsed = JSON.parse(script.textContent || "{}");
      roots.push(...asArray(parsed));
    } catch (_error) {
      // Ignore malformed publisher JSON-LD blocks.
    }
  }
  const flattened = [];
  const visit = (node) => {
    if (!node || typeof node !== "object") return;
    flattened.push(node);
    for (const child of asArray(node["@graph"])) visit(child);
    for (const child of asArray(node.mainEntity)) visit(child);
  };
  roots.forEach(visit);
  return flattened;
}

function extractFromPage() {
  const metas = [...document.querySelectorAll("meta")];
  const byName = (names) => {
    const lowered = names.map((name) => name.toLowerCase());
    return metas
      .filter((meta) => lowered.includes((meta.getAttribute("name") || meta.getAttribute("property") || "").toLowerCase()))
      .map((meta) => meta.getAttribute("content") || "")
      .filter(Boolean);
  };
  const first = (names) => byName(names)[0] || "";
  const jsonLdObjects = extractJsonLdObjects();
  const scholarly = jsonLdObjects.find((item) => {
    const type = asArray(item["@type"]).join(" ").toLowerCase();
    return /scholarlyarticle|article|creativework/.test(type) || item.doi || item.identifier;
  }) || {};
  const identifiers = asArray(scholarly.identifier).map(textFromJsonLd).join(" ");
  const jsonLdDoi = scholarly.doi || identifiers.match(DOI_RE)?.[0] || "";
  const jsonLdJournal = textFromJsonLd(scholarly.isPartOf) || textFromJsonLd(scholarly.publisher);
  const jsonLdAuthors = asArray(scholarly.author || scholarly.creator).map(textFromJsonLd);
  const links = [...document.querySelectorAll("a[href], link[href]")]
    .map((node) => node.href || node.getAttribute("href") || "")
    .filter((href) => /\.pdf(?:$|[?#])|pdf|full|pdfplus/i.test(href));
  const citationPdf = byName(["citation_pdf_url"]);
  const textDoi = (document.body?.innerText || location.href).match(DOI_RE)?.[0] || "";
  const pageDoi = normalizeDoi(first(["citation_doi", "dc.identifier", "dc.identifier.doi", "prism.doi"]) || jsonLdDoi || textDoi || location.href);
  const derivedPdfCandidates = [];
  if (location.hostname === "pubs.acs.org" && pageDoi) {
    derivedPdfCandidates.push(`https://pubs.acs.org/doi/pdfplus/${pageDoi}`);
    derivedPdfCandidates.push(`https://pubs.acs.org/doi/pdf/${pageDoi}`);
  }
  const title = first(["citation_title", "dc.title", "dcterms.title", "og:title", "twitter:title"])
    || scholarly.headline
    || scholarly.name
    || document.title;

  return {
    url: location.href,
    title: String(title || "").trim(),
    authors: unique([
      ...byName(["citation_author", "dc.creator", "dcterms.creator", "article:author"]),
      ...jsonLdAuthors,
    ]),
    journal: first(["citation_journal_title", "prism.publicationName", "dc.source", "dcterms.source", "og:site_name"])
      || jsonLdJournal,
    year: first(["citation_publication_date", "citation_online_date", "dc.date", "dcterms.issued", "article:published_time"])
      || scholarly.datePublished
      || scholarly.dateCreated,
    doi: pageDoi,
    abstract: first(["citation_abstract", "dc.description", "dcterms.abstract", "description", "og:description"])
      || scholarly.abstract
      || scholarly.description
      || "",
    pdfCandidates: unique([...derivedPdfCandidates, ...citationPdf, ...links]),
    metadata: {
      title,
      citation_authors: byName(["citation_author"]),
      citation_journal_title: first(["citation_journal_title"]),
      citation_publication_date: first(["citation_publication_date"]),
      citation_doi: normalizeDoi(first(["citation_doi"])),
      jsonld_doi: normalizeDoi(jsonLdDoi),
      citation_pdf_url: citationPdf,
    },
  };
}

async function getActiveTabPayload() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) {
    throw new Error("No active tab found.");
  }
  try {
    const injection = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: extractFromPage });
    return normalizePayload(injection?.[0]?.result, tab);
  } catch (error) {
    return normalizePayload(null, tab);
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
  if (response.status === 401 && !retried) {
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
    normalizeDoi,
    normalizePayload,
    renderVersionLine,
    setAuthenticated,
  };
} else {
  bootPopup();
}


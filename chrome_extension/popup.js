const DEFAULT_API_BASE = "https://word-addin-sooty.vercel.app";
const DEFAULT_APP_URL = "https://bunken-h56cct98ayvusf55qxwewt.streamlit.app";
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
  $("title").textContent = currentPayload.title || "Title not found";
  $("meta").textContent = [currentPayload.authors.join(", "), currentPayload.journal, currentPayload.year].filter(Boolean).join(" / ");
  $("doi").textContent = currentPayload.doi ? `DOI: ${currentPayload.doi}` : "DOI: not found";
  lastPdfCandidate = currentPayload.pdfCandidates[0] || "";
  $("openPdf").disabled = !lastPdfCandidate;
  $("pdf").textContent = lastPdfCandidate
    ? `PDF candidates: ${currentPayload.pdfCandidates.length} / ${lastPdfCandidate}`
    : `PDF candidates: ${currentPayload.pdfCandidates.length}`;
}

async function loadSettings() {
  const values = await chrome.storage.sync.get(["apiBase", "appUrl", "accessToken", "refreshToken", "email"]);
  $("apiBase").value = values.apiBase || DEFAULT_API_BASE;
  $("appUrl").value = values.appUrl || DEFAULT_APP_URL;
  $("accessToken").value = values.accessToken || "";
  $("email").value = values.email || "";
  $("status").textContent = values.accessToken || values.refreshToken ? "Signed in" : "Not connected";
}

async function saveSettings() {
  await chrome.storage.sync.set({
    apiBase: $("apiBase").value.trim().replace(/\/$/, ""),
    appUrl: $("appUrl").value.trim().replace(/\/$/, ""),
    accessToken: $("accessToken").value.trim(),
    email: $("email").value.trim(),
  });
}

async function refreshSession() {
  const values = await chrome.storage.sync.get(["apiBase", "refreshToken"]);
  const apiBase = (values.apiBase || DEFAULT_API_BASE).trim().replace(/\/$/, "");
  const refreshToken = values.refreshToken || "";
  if (!refreshToken) return "";
  const response = await fetch(`${apiBase}/api/addin/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refreshToken }),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok || !result.accessToken) return "";
  $("accessToken").value = result.accessToken;
  await chrome.storage.sync.set({
    accessToken: result.accessToken,
    refreshToken: result.refreshToken || refreshToken,
    email: result.email || $("email").value.trim(),
  });
  $("status").textContent = "Signed in";
  return result.accessToken;
}

async function getAccessToken() {
  let token = $("accessToken").value.trim();
  if (token) return token;
  token = await refreshSession();
  return token;
}

async function openPdfCandidate() {
  if (!lastPdfCandidate && currentPayload?.pdfCandidates?.length) {
    lastPdfCandidate = currentPayload.pdfCandidates[0];
  }
  if (!lastPdfCandidate) {
    $("message").textContent = "No PDF candidate found on this page.";
    return;
  }
  await chrome.tabs.create({ url: lastPdfCandidate });
}

async function openApp() {
  await saveSettings();
  const appUrl = $("appUrl").value.trim() || DEFAULT_APP_URL;
  await chrome.tabs.create({ url: appUrl });
}

async function login() {
  await saveSettings();
  const apiBase = $("apiBase").value.trim().replace(/\/$/, "");
  const email = $("email").value.trim();
  const password = $("password").value;
  if (!apiBase || !email || !password) {
    $("message").textContent = "Enter API URL, email, and password.";
    return;
  }
  $("message").textContent = "Signing in...";
  const response = await fetch(`${apiBase}/api/addin/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok || !result.accessToken) {
    $("message").textContent = `Sign in failed: ${result.error || response.status}`;
    return;
  }
  $("accessToken").value = result.accessToken;
  $("password").value = "";
  await saveSettings();
  await chrome.storage.sync.set({ refreshToken: result.refreshToken || "" });
  $("status").textContent = "Signed in";
  $("message").textContent = "Signed in. You can save this paper.";
}

async function extract() {
  $("message").textContent = "Extracting metadata from this page...";
  const payload = await getActiveTabPayload();
  render(payload);
  if (!currentPayload.title && !currentPayload.doi) {
    $("message").textContent = "Could not extract a title or DOI from this page. Open a paper landing page, then refresh.";
    return false;
  }
  $("message").textContent = "Metadata extracted. Review and save.";
  return true;
}

async function save(retried = false) {
  await saveSettings();
  if (!currentPayload) {
    const extracted = await extract();
    if (!extracted) return;
  }
  if (!currentPayload.title && !currentPayload.doi) {
    $("message").textContent = "Cannot save because this page has no title or DOI. Open a paper landing page, then refresh.";
    return;
  }
  const apiBase = $("apiBase").value.trim().replace(/\/$/, "");
  const token = await getAccessToken();
  if (!apiBase || !token) {
    $("message").textContent = "Sign in once. After that, bunken will keep you signed in automatically.";
    return;
  }
  $("message").textContent = "Saving to bunken...";
  const response = await fetch(`${apiBase}/api/addin/extension/save`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(currentPayload),
  });
  let result = await response.json().catch(() => ({}));
  if (response.status === 401 && !retried && await refreshSession()) {
    return save(true);
  }
  if (!response.ok) {
    $("message").textContent = `Save failed: ${result.error || response.status}`;
    return;
  }
  const lines = [result.duplicate ? "Already exists in bunken." : "Saved to bunken."];
  if (result.pdf?.saved) lines.push(`PDF saved: ${result.pdf.storagePath}`);
  else if (result.pdfCandidates?.length) {
    lastPdfCandidate = result.pdfCandidates[0];
    $("openPdf").disabled = false;
    lines.push(`PDF candidate: ${result.pdfCandidates[0]}`);
    lines.push("Open bunken app and use the paper detail pane to upload the PDF manually if needed.");
  }
  $("message").textContent = lines.join("\n");
}

$("extract").addEventListener("click", () => extract().catch((error) => { $("message").textContent = String(error); }));
$("login").addEventListener("click", () => login().catch((error) => { $("message").textContent = String(error); }));
$("save").addEventListener("click", () => save().catch((error) => { $("message").textContent = String(error); }));
$("openPdf").addEventListener("click", () => openPdfCandidate().catch((error) => { $("message").textContent = String(error); }));
$("openApp").addEventListener("click", () => openApp().catch((error) => { $("message").textContent = String(error); }));

loadSettings().then(extract).catch((error) => { $("message").textContent = String(error); });


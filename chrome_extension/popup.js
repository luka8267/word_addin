const DEFAULT_API_BASE = "https://word-addin-sooty.vercel.app";
const DOI_RE = /10\.\d{4,9}\/[-._;()/:A-Z0-9]+/i;

const $ = (id) => document.getElementById(id);
let currentPayload = null;

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
  const links = [...document.querySelectorAll("a[href], link[href]")]
    .map((node) => node.href || node.getAttribute("href") || "")
    .filter((href) => /\.pdf(?:$|[?#])|pdf/i.test(href));
  const citationPdf = byName(["citation_pdf_url"]);
  const textDoi = (document.body?.innerText || location.href).match(DOI_RE)?.[0] || "";
  const title = first(["citation_title", "dc.title", "dcterms.title", "og:title"]) || document.title;

  return {
    url: location.href,
    title: title.trim(),
    authors: unique(byName(["citation_author", "dc.creator", "dcterms.creator"])),
    journal: first(["citation_journal_title", "prism.publicationName", "dc.source", "og:site_name"]),
    year: first(["citation_publication_date", "citation_online_date", "dc.date", "dcterms.issued"]),
    doi: normalizeDoi(first(["citation_doi", "dc.identifier", "dc.identifier.doi"]) || textDoi),
    abstract: first(["citation_abstract", "dc.description", "description", "og:description"]),
    pdfCandidates: unique([...citationPdf, ...links]),
    metadata: {
      title,
      citation_authors: byName(["citation_author"]),
      citation_journal_title: first(["citation_journal_title"]),
      citation_publication_date: first(["citation_publication_date"]),
      citation_doi: normalizeDoi(first(["citation_doi"])),
      citation_pdf_url: citationPdf,
    },
  };
}

async function getActiveTabPayload() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const [{ result }] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: extractFromPage });
  return result;
}

function render(payload) {
  currentPayload = payload;
  $("preview").hidden = false;
  $("title").textContent = payload.title || "Title not found";
  $("meta").textContent = [payload.authors?.join(", "), payload.journal, payload.year].filter(Boolean).join(" / ");
  $("doi").textContent = payload.doi ? `DOI: ${payload.doi}` : "DOI: not found";
  $("pdf").textContent = `PDF candidates: ${payload.pdfCandidates?.length || 0}`;
}

async function loadSettings() {
  const values = await chrome.storage.sync.get(["apiBase", "accessToken", "email"]);
  $("apiBase").value = values.apiBase || DEFAULT_API_BASE;
  $("accessToken").value = values.accessToken || "";
  $("email").value = values.email || "";
  $("status").textContent = values.accessToken ? "Signed in" : "Not connected";
}

async function saveSettings() {
  await chrome.storage.sync.set({
    apiBase: $("apiBase").value.trim().replace(/\/$/, ""),
    accessToken: $("accessToken").value.trim(),
    email: $("email").value.trim(),
  });
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
  $("status").textContent = "Signed in";
  $("message").textContent = "Signed in. You can save this paper.";
}

async function extract() {
  $("message").textContent = "Extracting metadata from this page...";
  const payload = await getActiveTabPayload();
  render(payload);
  $("message").textContent = "Metadata extracted. Review and save.";
}

async function save() {
  await saveSettings();
  if (!currentPayload) await extract();
  const apiBase = $("apiBase").value.trim().replace(/\/$/, "");
  const token = $("accessToken").value.trim();
  if (!apiBase || !token) {
    $("message").textContent = "Enter API URL and access token, or sign in first.";
    return;
  }
  $("message").textContent = "Saving to bunken...";
  const response = await fetch(`${apiBase}/api/extension/save`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(currentPayload),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    $("message").textContent = `Save failed: ${result.error || response.status}`;
    return;
  }
  const lines = [result.duplicate ? "Already exists in bunken." : "Saved to bunken."];
  if (result.pdf?.saved) lines.push(`PDF saved: ${result.pdf.storagePath}`);
  else if (result.pdfCandidates?.length) lines.push(`PDF candidate: ${result.pdfCandidates[0]}`);
  $("message").textContent = lines.join("\n");
}

$("extract").addEventListener("click", () => extract().catch((error) => { $("message").textContent = String(error); }));
$("login").addEventListener("click", () => login().catch((error) => { $("message").textContent = String(error); }));
$("save").addEventListener("click", () => save().catch((error) => { $("message").textContent = String(error); }));

loadSettings().then(extract).catch((error) => { $("message").textContent = String(error); });

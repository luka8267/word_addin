(function () {
const DOI_RE = /10\.\d{4,9}\/[-._;+()/:<>A-Z0-9]+/i;

function cleanMetadataText(value) {
  const text = String(value ?? "").trim();
  return /^(nan|none|null|<na>|nat)$/i.test(text) ? "" : text;
}

function cleanPaperTitle(value, journal = "") {
  let text = cleanMetadataText(value);
  const template = document.createElement("template");
  template.innerHTML = text;
  template.content.querySelectorAll("script, style").forEach(node => node.remove());
  text = template.content.textContent;
  text = text.replace(/(\b[A-Z][a-z]?)\uf8ff(?=[A-Z][a-z]?\b)/g, "$1-");
  text = text.replace(/(?:\$\$|\$)?\\pi\s*(?:\$\$|\$)?/g, "π");
  text = text.replace(/\s*\|(?:[^|]*\|)?\s*(?:Springer Nature Link|SpringerLink)\s*$/i, "");
  const parts = text.split(/\s+-\s+/);
  if (parts.length >= 5 && parts.at(-1).toLowerCase() === "wiley online library" && /^\d{4}$/.test(parts.at(-3))) text = parts.slice(0, -4).join(" - ");
  if (journal) {
    const suffix = `| ${journal}`;
    if (text.trim().toLowerCase().endsWith(suffix.toLowerCase())) text = text.trim().slice(0, -suffix.length);
  }
  return text.replace(/\s+/g, " ").trim();
}

function normalizeDoi(value) {
  let decoded = String(value || "");
  try { decoded = decodeURIComponent(decoded); } catch (_error) { /* Keep malformed percent escapes intact. */ }
  const text = decoded
    .replace(/^doi:\s*/i, "")
    .replace(/^(?:https?:\/\/)?(dx\.)?doi\.org\//i, "")
    .trim();
  const match = text.match(DOI_RE);
  let doi = match ? match[0].replace(/[.,;]+$/, "") : text.replace(/[.,;]+$/, "");
  if (/^https?:\/\/(?:www\.)?degruyter(?:brill)?\.com\//i.test(decoded)) doi = doi.replace(/\/html$/i, "");
  return doi;
}

function unique(values) {
  return [...new Set(values.filter(Boolean).map((value) => String(value).trim()).filter(Boolean))];
}

function splitPersonList(values) {
  return unique(asArray(values).flatMap((value) => {
    const text = String(value || "").trim();
    if (!text) return [];
    return text
      .split(/\s*(?:;|\||\n|\band\b)\s*/i)
      .map((part) => part.trim())
      .filter(Boolean);
  }));
}

function isLikelyPaperPayload(value) {
  const payload = value && typeof value === "object" ? value : {};
  const metadata = payload.metadata && typeof payload.metadata === "object" ? payload.metadata : {};
  const doi = normalizeDoi(
    payload.doi
      || metadata.citation_doi
      || metadata.jsonld_doi
      || payload.url
      || "",
  );
  if (doi && DOI_RE.test(doi)) return true;
  if (payload.isLikelyPaper || metadata.jsonld_is_scholarly) return true;

  const citationAuthors = Array.isArray(metadata.citation_authors)
    ? metadata.citation_authors
    : [];
  const hasCitationTitle = Boolean(metadata.citation_title);
  const hasCitationContext = Boolean(
    citationAuthors.length
      || metadata.citation_journal_title
      || metadata.citation_publication_date
      || (Array.isArray(metadata.citation_pdf_url) && metadata.citation_pdf_url.length)
  );
  return hasCitationTitle && hasCitationContext;
}

function asArray(value) {
  return Array.isArray(value) ? value : value ? [value] : [];
}

function textFromJsonLd(value) {
  if (!value) return "";
  if (typeof value === "string") return value;
  if (typeof value === "object") {
    return value.value
      || [value.givenName, value.familyName].filter(Boolean).join(" ")
      || value.name
      || value.headline
      || value.title
      || value["@id"]
      || value.url
      || "";
  }
  return String(value || "");
}

function firstDoiFromValues(values) {
  for (const value of values || []) {
    const doi = normalizeDoi(value);
    if (doi && DOI_RE.test(doi)) return doi;
  }
  return "";
}

function isBlockedOrErrorPageTitle(value) {
  return /^(just a moment|checking your browser|page not found|page unavailable|access denied|forbidden|error)\b/i
    .test(String(value || "").trim());
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
      .filter((meta) => lowered.includes(
        (
          meta.getAttribute("name")
          || meta.getAttribute("property")
          || meta.getAttribute("itemprop")
          || ""
        ).toLowerCase()
      ))
      .map((meta) => cleanMetadataText(meta.getAttribute("content")))
      .filter(Boolean);
  };
  const first = (names) => names.map(name => byName([name])[0]).find(Boolean) || "";
  const allLinks = [...document.querySelectorAll("a[href], link[href]")];
  const jsonLdObjects = extractJsonLdObjects();
  const scholarly = jsonLdObjects.find(item => /scholarlyarticle/i.test(asArray(item["@type"]).join(" ")))
    || jsonLdObjects.find((item) => {
    const type = asArray(item["@type"]).join(" ").toLowerCase();
    return /\barticle\b/.test(type) || item.doi;
  }) || {};
  const scholarlyType = asArray(scholarly["@type"]).join(" ").toLowerCase();
  const jsonLdIsScholarly = /scholarlyarticle/.test(scholarlyType) || Boolean(scholarly.doi);
  const identifiers = asArray(scholarly.identifier).map(textFromJsonLd).join(" ");
  const jsonLdDoi = scholarly.doi || identifiers.match(DOI_RE)?.[0] || "";
  const parent = scholarly.isPartOf || {};
  const ancestry = [];
  let ancestor = parent;
  for (let depth = 0; depth < 5 && ancestor && typeof ancestor === "object"; depth += 1) {
    ancestry.push(ancestor);
    ancestor = ancestor.isPartOf;
  }
  const periodical = ancestry.find(item => /periodical/i.test(asArray(item["@type"]).join(" ")));
  const jsonLdJournal = textFromJsonLd(periodical || ancestry.at(-1) || parent);
  const jsonLdAuthors = asArray(scholarly.author || scholarly.creator).map(textFromJsonLd);
  const links = allLinks
    .filter((node) => {
      const href = node.href || node.getAttribute("href") || "";
      const label = [
        node.textContent,
        node.getAttribute("aria-label"),
        node.getAttribute("title"),
        node.getAttribute("type"),
        node.getAttribute("rel"),
      ].join(" ");
      return /\.pdf(?:$|[?#])|pdf|full|pdfplus|download/i.test(href)
        || /pdf|full text|download/i.test(label);
    })
    .map((node) => node.href || node.getAttribute("href") || "");
  const canonicalUrls = allLinks
    .filter((node) => /canonical/i.test(node.getAttribute("rel") || ""))
    .map((node) => node.href || node.getAttribute("href") || "");
  const doiLinkValues = allLinks
    .map((node) => node.href || node.getAttribute("href") || "")
    .filter((href) => /doi\.org\/10\.|\/doi\/10\./i.test(href));
  const citationPdf = byName(["citation_pdf_url", "dc.identifier", "prism.url", "wkhealth_pdf_url"])
    .filter((value) => /\.pdf(?:$|[?#])|pdf|full|pdfplus/i.test(value));
  const textDoi = (document.body?.innerText || location.href).match(DOI_RE)?.[0] || "";
  const pageDoiCandidate = firstDoiFromValues([
    first(["citation_doi", "dc.identifier", "dc.identifier.doi", "prism.doi", "bepress_citation_doi"]),
    jsonLdDoi,
    ...canonicalUrls,
    location.href,
    ...doiLinkValues,
    textDoi,
  ]);
  const pageDoi = DOI_RE.test(pageDoiCandidate) ? pageDoiCandidate : "";
  const derivedPdfCandidates = [];
  if (location.hostname === "pubs.acs.org" && pageDoi) {
    derivedPdfCandidates.push(`https://pubs.acs.org/doi/pdfplus/${pageDoi}`);
    derivedPdfCandidates.push(`https://pubs.acs.org/doi/pdf/${pageDoi}`);
  }
  if (/nature\.com$/i.test(location.hostname)) {
    const articleMatch = location.pathname.match(/\/articles\/([^/?#]+)/i);
    if (articleMatch) derivedPdfCandidates.push(`${location.origin}/articles/${articleMatch[1]}.pdf`);
  }
  if (/sciencedirect\.com$/i.test(location.hostname)) {
    const piiMatch = location.pathname.match(/\/pii\/([A-Z0-9]+)/i);
    if (piiMatch) derivedPdfCandidates.push(`${location.origin}/science/article/pii/${piiMatch[1]}/pdfft?download=true`);
  }
  if (/onlinelibrary\.wiley\.com$/i.test(location.hostname) && pageDoi) {
    derivedPdfCandidates.push(`${location.origin}/doi/pdfdirect/${pageDoi}`);
    derivedPdfCandidates.push(`${location.origin}/doi/pdf/${pageDoi}`);
  }
  if (/link\.springer\.com$/i.test(location.hostname) && pageDoi) {
    derivedPdfCandidates.push(`${location.origin}/content/pdf/${pageDoi}.pdf`);
  }
  if (/tandfonline\.com$/i.test(location.hostname) && pageDoi) {
    derivedPdfCandidates.push(`${location.origin}/doi/pdf/${pageDoi}`);
  }
  if (/journals\.plos\.org$/i.test(location.hostname)) {
    const articleId = new URLSearchParams(location.search).get("id");
    if (articleId) derivedPdfCandidates.push(`${location.origin}${location.pathname}?id=${articleId}&type=printable`);
  }
  const isGoogleScholarSearch = /(^|\.)scholar\.google\./i.test(location.hostname)
    && /\/scholar\b/i.test(location.pathname);
  const citationTitle = first(["citation_title", "dc.title", "dcterms.title"]);
  const citationJournal = first(["citation_journal_title", "prism.publicationName"]);
  const citationDate = first(["citation_cover_date", "citation_publication_date", "citation_date", "citation_year", "prism.publicationDate", "dc.date", "dcterms.issued"]);
  const metaFirstPage = cleanMetadataText(first(["citation_firstpage", "prism.startingPage"]));
  const firstPage = metaFirstPage || cleanMetadataText(scholarly.pageStart);
  const lastPage = metaFirstPage
    ? cleanMetadataText(first(["citation_lastpage", "prism.endingPage"]))
    : cleanMetadataText(scholarly.pageEnd);
  const descendingPages = /^\d+$/.test(firstPage) && /^\d+$/.test(lastPage) && Number(lastPage) < Number(firstPage);
  const pages = cleanMetadataText(first(["citation_article_number", "citation_elocation_id", "prism.articleNumber"]) || scholarly.articleNumber)
    || cleanMetadataText(first(["citation_pages", "prism.pageRange"]) || scholarly.pagination)
    || (firstPage && lastPage && firstPage !== lastPage && !descendingPages ? `${firstPage}-${lastPage}` : firstPage);
  const volume = cleanMetadataText(first(["citation_volume", "prism.volume"]) || ancestry.find(item => item.volumeNumber)?.volumeNumber);
  const issue = cleanMetadataText(first(["citation_issue", "prism.number", "prism.issueIdentifier", "prism.issueNumber"]) || ancestry.find(item => item.issueNumber)?.issueNumber);
  const publisher = first(["citation_publisher", "dc.publisher", "dcterms.publisher"])
    || textFromJsonLd(scholarly.publisher);
  const citationAuthors = splitPersonList([
    ...byName(["citation_author"]),
    ...byName(["citation_authors"]),
  ]);
  const title = cleanPaperTitle(citationTitle
    || scholarly.headline
    || scholarly.name
    || first(["og:title", "twitter:title"])
    || document.title, citationJournal || jsonLdJournal);
  const isBlockedOrErrorPage = isBlockedOrErrorPageTitle(title || document.title);
  const metadata = {
    title,
    citation_title: citationTitle,
    citation_authors: citationAuthors,
    citation_journal_title: citationJournal,
    citation_publication_date: citationDate,
    citation_doi: normalizeDoi(first(["citation_doi"])),
    jsonld_doi: normalizeDoi(jsonLdDoi),
    jsonld_is_scholarly: jsonLdIsScholarly,
    citation_pdf_url: citationPdf,
    volume,
    issue,
    pages,
    publisher,
  };

  return {
    url: location.href,
    title: String(title || "").trim(),
    authors: citationAuthors.length ? citationAuthors : (jsonLdAuthors.length ? unique(jsonLdAuthors) : splitPersonList(byName(["dc.creator", "dcterms.creator", "article:author", "parsely-author"]))),
    journal: citationJournal
      || jsonLdJournal
      || first(["citation_journal_abbrev", "dc.source", "dcterms.source", "og:site_name"]),
    year: citationDate
      || first(["citation_online_date", "dc.date", "dcterms.issued", "article:published_time"])
      || scholarly.datePublished
      || scholarly.dateCreated,
    doi: pageDoi,
    volume,
    issue,
    pages,
    publisher,
    abstract: first(["citation_abstract", "dc.description", "dcterms.abstract", "description", "og:description"])
      || scholarly.abstract
      || scholarly.description
      || "",
    pdfCandidates: unique([...derivedPdfCandidates, ...citationPdf, ...links]),
    isLikelyPaper: isLikelyPaperPayload({
      url: location.href,
      doi: pageDoi,
      metadata,
    }) && !isGoogleScholarSearch && !isBlockedOrErrorPage,
    metadata,
  };
}


const api = { DOI_RE, normalizeDoi, unique, splitPersonList, isLikelyPaperPayload, asArray, textFromJsonLd, firstDoiFromValues, isBlockedOrErrorPageTitle, extractJsonLdObjects, extractFromPage, cleanMetadataText, cleanPaperTitle };
if (typeof module !== "undefined" && module.exports) module.exports = api;
else globalThis.bunkenPageMetadata = api;
})();

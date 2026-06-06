const assert = require("node:assert/strict");
const {
  buildDerivedPdfCandidates,
  compareVersions,
  extractFromPage,
  isBlockedOrErrorPageTitle,
  isLikelyPaperPayload,
  normalizeDoi,
  normalizePayload,
  renderVersionLine,
  setAuthenticated,
  shouldRefreshAuth,
} = require("../chrome_extension/popup.js");

function meta(name, content, attr = "name") {
  return {
    getAttribute(key) {
      if (key === attr) return name;
      if (key === "content") return content;
      return "";
    },
  };
}

function link(href) {
  return {
    href,
    getAttribute(key) {
      return key === "href" ? href : "";
    },
  };
}

function linkWithAttributes(href, attributes = {}) {
  return {
    href,
    textContent: attributes.textContent || "",
    getAttribute(key) {
      if (key === "href") return href;
      return attributes[key] || "";
    },
  };
}

function script(json) {
  return { textContent: JSON.stringify(json) };
}

function installDocument({ metas = [], links = [], scripts = [], bodyText = "", title = "" }) {
  global.document = {
    title,
    body: { innerText: bodyText },
    querySelectorAll(selector) {
      if (selector === "meta") return metas;
      if (selector === 'script[type="application/ld+json"]') return scripts;
      if (selector === "a[href], link[href]") return links;
      return [];
    },
  };
}

function installLocation(url) {
  global.location = new URL(url);
}

function installPopupElements() {
  const elements = {
    authPanel: { hidden: false },
    importPanel: { hidden: true },
    status: { textContent: "" },
    versionLine: { textContent: "" },
  };
  global.document = {
    getElementById(id) {
      return elements[id] || null;
    },
  };
  return elements;
}

function installChromeRuntime(version = "0.2.9") {
  global.chrome = {
    runtime: {
      getManifest() {
        return { version };
      },
    },
  };
}

function testMetaAndJsonLdExtraction() {
  installLocation("https://example.org/articles/123");
  installDocument({
    title: "Fallback Browser Title",
    metas: [
      meta("citation_title", "Meta Title"),
      meta("citation_author", "Alice Author"),
      meta("citation_author", "Bob Author"),
      meta("citation_authors", "Carol Author; Dave Author"),
      meta("citation_journal_title", "Journal of Tests"),
      meta("citation_publication_date", "2026-05-27"),
      meta("citation_doi", "https://doi.org/10.1234/example.2026"),
      meta("citation_pdf_url", "https://example.org/paper.pdf"),
      meta("citation_volume", "12"),
      meta("citation_issue", "3"),
      meta("citation_firstpage", "45"),
      meta("citation_lastpage", "67"),
      meta("citation_publisher", "Example Publisher"),
      meta("description", "Abstract from meta."),
    ],
    scripts: [
      script({
        "@type": "ScholarlyArticle",
        author: [{ name: "Alice Author" }],
        doi: "10.1234/example.2026",
      }),
    ],
    links: [link("https://example.org/download/fulltext.pdf")],
  });

  const result = extractFromPage();
  assert.equal(result.url, "https://example.org/articles/123");
  assert.equal(result.title, "Meta Title");
  assert.deepEqual(result.authors, ["Alice Author", "Bob Author", "Carol Author", "Dave Author"]);
  assert.equal(result.journal, "Journal of Tests");
  assert.equal(result.year, "2026-05-27");
  assert.equal(result.doi, "10.1234/example.2026");
  assert.equal(result.volume, "12");
  assert.equal(result.issue, "3");
  assert.equal(result.pages, "45-67");
  assert.equal(result.publisher, "Example Publisher");
  assert.equal(result.isLikelyPaper, true);
  assert.equal(result.abstract, "Abstract from meta.");
  assert.deepEqual(result.pdfCandidates, [
    "https://example.org/paper.pdf",
    "https://example.org/download/fulltext.pdf",
  ]);
}

function testAcsDerivedPdfCandidates() {
  installLocation("https://pubs.acs.org/doi/10.1021/jp512766r");
  installDocument({
    title: "ACS Landing",
    metas: [meta("citation_doi", "10.1021/jp512766r")],
  });

  const result = extractFromPage();
  assert.equal(result.doi, "10.1021/jp512766r");
  assert.equal(result.isLikelyPaper, true);
  assert.equal(result.pdfCandidates[0], "https://pubs.acs.org/doi/pdfplus/10.1021/jp512766r");
  assert.equal(result.pdfCandidates[1], "https://pubs.acs.org/doi/pdf/10.1021/jp512766r");
}

function testPublisherDerivedPdfCandidates() {
  installLocation("https://www.nature.com/articles/s41586-020-2649-2");
  installDocument({
    title: "Nature Article",
    metas: [meta("citation_doi", "10.1038/s41586-020-2649-2")],
  });
  let result = extractFromPage();
  assert.equal(result.pdfCandidates[0], "https://www.nature.com/articles/s41586-020-2649-2.pdf");

  installLocation("https://www.sciencedirect.com/science/article/pii/S0167739X24001234");
  installDocument({
    title: "ScienceDirect Article",
    metas: [meta("citation_doi", "10.1016/j.example.2024.01.001")],
  });
  result = extractFromPage();
  assert.equal(
    result.pdfCandidates[0],
    "https://www.sciencedirect.com/science/article/pii/S0167739X24001234/pdfft?download=true",
  );

  installLocation("https://onlinelibrary.wiley.com/doi/abs/10.1002/anie.202400001");
  installDocument({
    title: "Wiley Article",
    metas: [meta("citation_doi", "10.1002/anie.202400001")],
  });
  result = extractFromPage();
  assert.equal(result.pdfCandidates[0], "https://onlinelibrary.wiley.com/doi/pdfdirect/10.1002/anie.202400001");

  installLocation("https://link.springer.com/article/10.1007/s00216-024-00001-1");
  installDocument({
    title: "Springer Article",
    metas: [meta("citation_doi", "10.1007/s00216-024-00001-1")],
  });
  result = extractFromPage();
  assert.equal(result.pdfCandidates[0], "https://link.springer.com/content/pdf/10.1007/s00216-024-00001-1.pdf");

  installLocation("https://www.tandfonline.com/doi/full/10.1080/00000000.2024.0000001");
  installDocument({
    title: "Taylor Article",
    metas: [meta("citation_doi", "10.1080/00000000.2024.0000001")],
  });
  result = extractFromPage();
  assert.equal(result.pdfCandidates[0], "https://www.tandfonline.com/doi/pdf/10.1080/00000000.2024.0000001");
}

function testDoiExtractionFromLinksCanonicalAndJsonLdValue() {
  installLocation("https://example.org/article-with-link-doi");
  installDocument({
    title: "DOI Link Article",
    metas: [meta("citation_title", "DOI Link Article"), meta("citation_author", "Alice Author")],
    links: [linkWithAttributes("https://doi.org/10.5555/link.doi")],
  });
  let result = extractFromPage();
  assert.equal(result.doi, "10.5555/link.doi");
  assert.equal(result.isLikelyPaper, true);

  installLocation("https://example.org/canonical");
  installDocument({
    title: "Canonical DOI Article",
    metas: [meta("citation_title", "Canonical DOI Article"), meta("citation_author", "Bob Author")],
    links: [linkWithAttributes("https://example.org/doi/10.5555/canonical.doi", { rel: "canonical" })],
  });
  result = extractFromPage();
  assert.equal(result.doi, "10.5555/canonical.doi");
  assert.equal(result.isLikelyPaper, true);

  installLocation("https://example.org/jsonld-property-value");
  installDocument({
    title: "JSON-LD DOI Article",
    scripts: [
      script({
        "@type": "ScholarlyArticle",
        headline: "JSON-LD DOI Article",
        author: [{ name: "Carol Author" }],
        identifier: [{ propertyID: "doi", value: "10.5555/jsonld.value" }],
      }),
    ],
  });
  result = extractFromPage();
  assert.equal(result.doi, "10.5555/jsonld.value");
  assert.equal(result.isLikelyPaper, true);
}

function testNormalizePayloadAddsRelativePdfCandidate() {
  const result = normalizePayload(
    {
      title: "Payload Title",
      url: "https://example.org/article",
      doi: "doi: 10.9999/test;",
      pdfCandidates: ["/paper.pdf"],
    },
    null,
  );
  assert.equal(result.doi, "10.9999/test");
  assert.equal(result.isLikelyPaper, true);
  assert.deepEqual(result.pdfCandidates, ["https://example.org/paper.pdf"]);
}

function testGenericWebPageIsNotLikelyPaper() {
  installLocation("https://example.org/about");
  installDocument({
    title: "About Example",
    metas: [
      meta("og:title", "About Example", "property"),
      meta("description", "A normal website page."),
    ],
    links: [link("https://example.org/brochure.pdf")],
    bodyText: "This is not an academic paper.",
  });

  const result = extractFromPage();
  assert.equal(result.title, "About Example");
  assert.equal(result.doi, "");
  assert.equal(result.isLikelyPaper, false);
  assert.equal(normalizePayload(null, { title: "Browser Title", url: "https://example.org" }).isLikelyPaper, false);
}

function testGoogleScholarSearchPageIsNotSavedAsPaper() {
  installLocation("https://scholar.google.com/scholar?q=10.1021%2Fjp512766r");
  installDocument({
    title: "Google Scholar Search",
    bodyText: "10.1021/jp512766r search results",
  });

  const result = extractFromPage();
  assert.equal(result.doi, "10.1021/jp512766r");
  assert.equal(result.isLikelyPaper, false);
}

function testBlockedOrErrorPagesAreNotSavedAsPaper() {
  installLocation("https://onlinelibrary.wiley.com/doi/10.1002/anie.202400001");
  installDocument({
    title: "Just a moment...",
    bodyText: "10.1002/anie.202400001",
  });
  let result = extractFromPage();
  assert.equal(result.doi, "10.1002/anie.202400001");
  assert.equal(result.isLikelyPaper, false);

  installLocation("https://link.springer.com/article/10.1007/s00216-024-00001-1");
  installDocument({
    title: "Page Unavailable | Springer Nature Link",
    bodyText: "10.1007/s00216-024-00001-1",
  });
  result = extractFromPage();
  assert.equal(result.doi, "10.1007/s00216-024-00001-1");
  assert.equal(result.isLikelyPaper, false);
}

function testHelpers() {
  assert.equal(normalizeDoi("https://dx.doi.org/10.5555/abc."), "10.5555/abc");
  assert.equal(isLikelyPaperPayload({ url: "https://doi.org/10.5555/abc" }), true);
  assert.equal(isLikelyPaperPayload({ title: "Just a page", url: "https://example.org" }), false);
  assert.equal(
    isLikelyPaperPayload({
      metadata: {
        citation_title: "Paper title",
        citation_authors: ["Alice"],
      },
    }),
    true,
  );
  assert.equal(compareVersions("0.2.10", "0.2.4") > 0, true);
  assert.equal(isBlockedOrErrorPageTitle("Just a moment..."), true);
  assert.equal(isBlockedOrErrorPageTitle("Page not found"), true);
  assert.equal(isBlockedOrErrorPageTitle("Array programming with NumPy"), false);
  assert.deepEqual(
    buildDerivedPdfCandidates(
      { pdfCandidates: ["https://pubs.acs.org/doi/pdf/10.1021/jp512766r"] },
      "https://pubs.acs.org/doi/10.1021/jp512766r",
      "10.1021/jp512766r",
    ),
    [
      "https://pubs.acs.org/doi/pdfplus/10.1021/jp512766r",
      "https://pubs.acs.org/doi/pdf/10.1021/jp512766r",
    ],
  );
}

function testExpiredAuthDetection() {
  assert.equal(shouldRefreshAuth({ status: 401 }, { error: "Authentication expired" }), true);
  assert.equal(
    shouldRefreshAuth(
      { status: 403 },
      { error: 'Supabase request failed: 403 {"error_code":"bad_jwt","msg":"token is expired"}' },
    ),
    true,
  );
  assert.equal(shouldRefreshAuth({ status: 403 }, { error: "RLS denied" }), false);
  assert.equal(shouldRefreshAuth({ status: 500 }, { error: "token is expired" }), false);
}

function testAuthenticatedUiState() {
  const elements = installPopupElements();
  setAuthenticated(false);
  assert.equal(elements.authPanel.hidden, false);
  assert.equal(elements.importPanel.hidden, true);
  assert.equal(elements.status.textContent, "未接続");

  setAuthenticated(true);
  assert.equal(elements.authPanel.hidden, true);
  assert.equal(elements.importPanel.hidden, false);
  assert.equal(elements.status.textContent, "ログイン済み");
}

function testVersionLine() {
  const elements = installPopupElements();
  installChromeRuntime("0.2.9");
  renderVersionLine();
  assert.equal(elements.versionLine.textContent, "v0.2.9");
}

testMetaAndJsonLdExtraction();
testAcsDerivedPdfCandidates();
testPublisherDerivedPdfCandidates();
testDoiExtractionFromLinksCanonicalAndJsonLdValue();
testNormalizePayloadAddsRelativePdfCandidate();
testGenericWebPageIsNotLikelyPaper();
testGoogleScholarSearchPageIsNotSavedAsPaper();
testBlockedOrErrorPagesAreNotSavedAsPaper();
testHelpers();
testExpiredAuthDetection();
testAuthenticatedUiState();
testVersionLine();
console.log("Chrome extension extraction tests passed");

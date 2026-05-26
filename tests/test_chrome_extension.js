const assert = require("node:assert/strict");
const {
  buildDerivedPdfCandidates,
  compareVersions,
  extractFromPage,
  normalizeDoi,
  normalizePayload,
  renderVersionLine,
  setAuthenticated,
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
      meta("citation_journal_title", "Journal of Tests"),
      meta("citation_publication_date", "2026-05-27"),
      meta("citation_doi", "https://doi.org/10.1234/example.2026"),
      meta("citation_pdf_url", "https://example.org/paper.pdf"),
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
  assert.deepEqual(result.authors, ["Alice Author", "Bob Author"]);
  assert.equal(result.journal, "Journal of Tests");
  assert.equal(result.year, "2026-05-27");
  assert.equal(result.doi, "10.1234/example.2026");
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
  assert.equal(result.pdfCandidates[0], "https://pubs.acs.org/doi/pdfplus/10.1021/jp512766r");
  assert.equal(result.pdfCandidates[1], "https://pubs.acs.org/doi/pdf/10.1021/jp512766r");
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
  assert.deepEqual(result.pdfCandidates, ["https://example.org/paper.pdf"]);
}

function testHelpers() {
  assert.equal(normalizeDoi("https://dx.doi.org/10.5555/abc."), "10.5555/abc");
  assert.equal(compareVersions("0.2.10", "0.2.4") > 0, true);
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
testNormalizePayloadAddsRelativePdfCandidate();
testHelpers();
testAuthenticatedUiState();
testVersionLine();
console.log("Chrome extension extraction tests passed");

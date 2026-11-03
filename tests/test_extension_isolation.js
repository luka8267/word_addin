const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const test = require("node:test");
const { JSDOM } = require("jsdom");
const { getActiveTabPayload } = require("../chrome_extension/popup.js");
const { cleanPaperTitle, normalizeDoi } = require("../chrome_extension/extractor.js");

function createTab(html, url) {
  const dom = new JSDOM(html, { url });
  const context = vm.createContext({ document: dom.window.document, location: new URL(url), URL, URLSearchParams });
  const calls = [];
  global.chrome = {
    tabs: { query: async () => [{ id: 1, url, title: dom.window.document.title }] },
    scripting: { executeScript: async (options) => {
      calls.push(options);
      if (options.files) {
        for (const file of options.files) {
          vm.runInContext(fs.readFileSync(path.join(__dirname, "../chrome_extension", file), "utf8"), context);
        }
        return [];
      }
      // Chrome serializes functions. No popup scope or helpers exist in this VM.
      return [{ result: JSON.parse(JSON.stringify(vm.runInContext(`(${options.func.toString()})()`, context))) }];
    } },
  };
  return { dom, calls };
}

test("actual isolated injection loads every dependency and preserves DOI plus", async () => {
  const tab = createTab(`<title>Wrong browser title</title><meta name="citation_title" content="Exact title"><meta name="citation_author" content="R. Scott Rowland"><meta name="citation_journal_title" content="Journal"><meta name="citation_doi" content="10.1021/jp953141+">`, "https://pubs.acs.org/doi/10.1021/jp953141%2B");
  const result = await getActiveTabPayload();
  assert.equal(result.title, "Exact title");
  assert.deepEqual(result.authors, ["R. Scott Rowland"]);
  assert.equal(result.doi, "10.1021/jp953141+");
  assert.deepEqual(tab.calls[0].files, ["extractor.js"]);
  assert.equal(result.isLikelyPaper, true);
  tab.dom.window.close();
});

test("JSON-LD keeps full names, article number, journal hierarchy and main-page DOI", async () => {
  const article = { "@type": "ScholarlyArticle", headline: "Correct title", author: [{ givenName: "Andrei V.", familyName: "Afonin" }, { name: "Danuta Rusinska-Roszak" }], articleNumber: "0018", isPartOf: { "@type": "PublicationIssue", issueNumber: "1", isPartOf: { "@type": "PublicationVolume", volumeNumber: "30", isPartOf: { "@type": "Periodical", name: "Journal of Molecular Modeling" } } } };
  const tab = createTab(`<title>Browser title | Springer Nature Link</title><script type="application/ld+json">${JSON.stringify({ "@graph": [{ "@type": "WebPage", identifier: "page" }, article] })}</script><a href="https://doi.org/10.1234/reference">Reference</a>`, "https://link.springer.com/article/10.1007/s00894-023-05811-1");
  const result = await getActiveTabPayload();
  assert.equal(result.doi, "10.1007/s00894-023-05811-1");
  assert.equal(result.title, "Correct title");
  assert.equal(result.pages, "0018");
  assert.equal(result.journal, "Journal of Molecular Modeling");
  assert.deepEqual(result.authors, ["Andrei V. Afonin", "Danuta Rusinska-Roszak"]);
  assert.equal(result.volume, "30");
  assert.equal(result.issue, "1");
  tab.dom.window.close();
});

test("publisher browser-title pollution, math markup and nan are cleaned", async () => {
  const tab = createTab(`<title>Modeling $$\\pi$$ interactions | Theoretical Chemistry Accounts | Springer Nature Link</title><meta name="citation_article_number" content="174"><meta name="citation_firstpage" content="nan"><meta name="citation_publisher" content="nan">`, "https://example.test/doi/10.1234/test");
  const result = await getActiveTabPayload();
  assert.equal(result.title, "Modeling π interactions");
  assert.equal(result.pages, "174");
  assert.equal(result.publisher, "");
  global.document = tab.dom.window.document;
  assert.equal(cleanPaperTitle("An insight into C\uf8ffH···N"), "An insight into C-H···N");
  assert.equal(cleanPaperTitle("A title - with a subtitle - Saleh - 2012 - Chemistry – A European Journal - Wiley Online Library"), "A title - with a subtitle");
  assert.equal(normalizeDoi("https://www.degruyterbrill.com/document/doi/10.1515/pac-2025-0555/html"), "10.1515/pac-2025-0555");
  tab.dom.window.close();
});

test("injection failures do not silently turn into title-only saves", async () => {
  global.chrome = { tabs: { query: async () => [{ id: 1, title: "Only title", url: "https://example.test" }] }, scripting: { executeScript: async () => { throw new Error("denied"); } } };
  await assert.rejects(getActiveTabPayload(), /ページ情報を読み取れませんでした/);
});

test("Springer article number is not joined to the JSON-LD page count and print date wins", async () => {
  const article = { "@type": "ScholarlyArticle", headline: "Correct title", pageStart: "1", pageEnd: "13" };
  const tab = createTab(`<meta name="prism.publicationDate" content="2023-12-30"><meta name="citation_publication_date" content="2024/01"><meta name="citation_firstpage" content="18"><meta name="citation_lastpage" content=""><script type="application/ld+json">${JSON.stringify(article)}</script>`, "https://link.springer.com/article/10.1007/s00894-023-05811-1");
  const result = await getActiveTabPayload();
  assert.equal(result.pages, "18");
  assert.equal(result.year, "2024/01");
  tab.dom.window.close();
});

test("popup and app download package both include the standalone extractor", () => {
  const html = fs.readFileSync(path.join(__dirname, "../chrome_extension/popup.html"), "utf8");
  assert.ok(html.indexOf('src="extractor.js"') < html.indexOf('src="popup.js"'));
  assert.ok(html.includes('src="extractor.js"'));
});

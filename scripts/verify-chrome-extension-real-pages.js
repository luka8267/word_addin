const { JSDOM } = require("jsdom");
const { extractFromPage } = require("../chrome_extension/popup.js");

const CASES = [
  {
    name: "ACS",
    url: "https://pubs.acs.org/doi/10.1021/jp512766r",
    expectDoi: "10.1021/jp512766r",
  },
  {
    name: "Nature",
    url: "https://www.nature.com/articles/s41586-020-2649-2",
  },
  {
    name: "ScienceDirect",
    url: "https://www.sciencedirect.com/science/article/pii/S0092867420306152",
  },
  {
    name: "PubMed",
    url: "https://pubmed.ncbi.nlm.nih.gov/32415295/",
  },
  {
    name: "Google Scholar",
    url: "https://scholar.google.com/scholar?q=10.1021%2Fjp512766r",
    allowBlocked: true,
    expectSearchPage: true,
  },
];

function installDom(html, url) {
  const dom = new JSDOM(html, { url });
  global.document = dom.window.document;
  global.location = dom.window.location;
}

async function fetchHtml(url) {
  const response = await fetch(url, {
    headers: {
      "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125 Safari/537.36 bunken-verifier/1.0",
      Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    },
  });
  const text = await response.text();
  return { status: response.status, text };
}

(async function main() {
  const results = [];
  for (const testCase of CASES) {
    try {
      const { status, text } = await fetchHtml(testCase.url);
      if (status >= 400) {
        results.push({ name: testCase.name, status, blocked: true });
        continue;
      }
      installDom(text, testCase.url);
      const payload = extractFromPage();
      results.push({
        name: testCase.name,
        status,
        title: payload.title,
        doi: payload.doi,
        authors: payload.authors.length,
        journal: payload.journal,
        year: payload.year,
        volume: payload.volume,
        issue: payload.issue,
        pages: payload.pages,
        publisher: payload.publisher,
        pdfCandidates: payload.pdfCandidates.length,
        isLikelyPaper: payload.isLikelyPaper,
      });
    } catch (error) {
      results.push({ name: testCase.name, error: error.message || String(error) });
    }
  }
  console.table(results);

  const actionableFailures = results.filter((result) => {
    if (result.blocked || result.error) {
      return false;
    }
    const testCase = CASES.find((item) => item.name === result.name);
    if (testCase && testCase.expectSearchPage) {
      return false;
    }
    return !result.isLikelyPaper || (!result.doi && !result.title);
  });
  if (actionableFailures.length) {
    process.exitCode = 1;
  }
})();

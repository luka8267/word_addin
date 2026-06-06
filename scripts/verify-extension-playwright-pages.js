const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

const repoRoot = path.resolve(__dirname, "..");
const popupSource = fs.readFileSync(path.join(repoRoot, "chrome_extension", "popup.js"), "utf8");

const CASES = [
  {
    name: "ACS",
    url: "https://pubs.acs.org/doi/10.1021/jp512766r",
    expectDoi: "10.1021/jp512766r",
  },
  {
    name: "Nature",
    url: "https://www.nature.com/articles/s41586-020-2649-2",
    expectDoi: "10.1038/s41586-020-2649-2",
  },
  {
    name: "ScienceDirect",
    url: "https://www.sciencedirect.com/science/article/pii/S0092867420306152",
    allowBlocked: true,
  },
  {
    name: "PubMed",
    url: "https://pubmed.ncbi.nlm.nih.gov/32415295/",
    expectDoi: "10.1038/s41477-020-0656-9",
    allowBlocked: true,
  },
  {
    name: "Wiley",
    url: "https://onlinelibrary.wiley.com/doi/abs/10.1002/anie.202405299",
    allowBlocked: true,
  },
  {
    name: "Springer",
    url: "https://link.springer.com/article/10.1007/s00216-024-05525-0",
  },
  {
    name: "TaylorFrancis",
    url: "https://www.tandfonline.com/doi/full/10.1080/23738871.2024.2422235",
  },
  {
    name: "PLOS",
    url: "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0300001",
  },
  {
    name: "GoogleScholarSearch",
    url: "https://scholar.google.com/scholar?q=10.1021%2Fjp512766r",
    expectNotPaper: true,
  },
];

function isBlockedVerifierPage(result) {
  return /^(just a moment|checking your browser|page not found|page unavailable|access denied|forbidden)\b/i
    .test(String(result.title || "").trim());
}

async function installExtractor(page) {
  await page.evaluate((source) => {
    const install = new Function(
      "source",
      `
        const module = { exports: {} };
        const exports = module.exports;
        eval(source);
        window.__bunkenExtractFromPage = module.exports.extractFromPage;
      `
    );
    install(source);
  }, popupSource);
}

async function extractCase(browser, testCase) {
  const page = await browser.newPage({
    userAgent:
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125 Safari/537.36 bunken-playwright-verifier/1.0",
  });
  try {
    const response = await page.goto(testCase.url, {
      waitUntil: "domcontentloaded",
      timeout: 45000,
    });
    await page.waitForTimeout(1500);
    await installExtractor(page);
    const payload = await page.evaluate(() => window.__bunkenExtractFromPage());
    return {
      name: testCase.name,
      status: response ? response.status() : 0,
      title: payload.title,
      doi: payload.doi,
      authors: payload.authors.length,
      journal: payload.journal,
      year: payload.year,
      pdfCandidates: payload.pdfCandidates.length,
      firstPdfCandidate: payload.pdfCandidates[0] || "",
      isLikelyPaper: payload.isLikelyPaper,
    };
  } catch (error) {
    return {
      name: testCase.name,
      error: error.message || String(error),
    };
  } finally {
    await page.close();
  }
}

(async function main() {
  const browser = await chromium.launch({ headless: true });
  try {
    const results = [];
    for (const testCase of CASES) {
      results.push(await extractCase(browser, testCase));
    }
    console.table(results);

    const failures = results.filter((result) => {
      const testCase = CASES.find((item) => item.name === result.name);
      if (!testCase || result.error) return true;
      if (testCase.expectNotPaper) return result.isLikelyPaper;
      if (testCase.allowBlocked && (result.status >= 400 || isBlockedVerifierPage(result))) return false;
      if (testCase.expectDoi && result.doi !== testCase.expectDoi) return true;
      return !result.isLikelyPaper || (!result.doi && !result.title);
    });
    if (failures.length) {
      console.error("Actionable failures:");
      console.error(JSON.stringify(failures, null, 2));
      process.exitCode = 1;
    }
  } finally {
    await browser.close();
  }
})();

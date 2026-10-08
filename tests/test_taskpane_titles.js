const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const { JSDOM } = require("jsdom");

const root = path.resolve(__dirname, "..");
const source = fs.readFileSync(path.join(root, "bunkenn/word-app/static/taskpane.js"), "utf8");
const html = fs.readFileSync(path.join(root, "bunkenn/word-app/static/taskpane.html"), "utf8");
const dom = new JSDOM(html, { url: "https://example.test", runScripts: "outside-only" });
dom.window.Office = { onReady() {} };
// Expose the production helpers only inside this test's in-memory script.
dom.window.eval(source.replace(/\}\)\(\);\s*$/, "globalThis.titleTests = { paperTitleText, renderPaperList, buildBibliographyHtml };})();"));
const { paperTitleText, renderPaperList, buildBibliographyHtml } = dom.window.titleTests;

test("decodes publisher markup and entities without corrupting Unicode", () => {
  assert.equal(paperTitleText("CH<sub>3</sub> &amp; Methyl&ndash;π"), "CH3 & Methyl–π");
  assert.equal(paperTitleText("C&lt;sub&gt;4&lt;/sub&gt; &amp;amp; H"), "C4 & H");
  assert.equal(paperTitleText("日本語 / Müller / α–β"), "日本語 / Müller / α–β");
  assert.equal(paperTitleText("Energy < 5 & pressure > 2"), "Energy < 5 & pressure > 2");
  assert.equal(paperTitleText(null), "");
});

test("renders title as inert text in the actual literature list", () => {
  const container = dom.window.document.createElement("div");
  renderPaperList(container, [{ id: "test", title: 'A &amp; B<script>throw new Error("unsafe")</script><img src=x onerror=alert(1)>', authors: "", journal: "", year: 2026 }]);
  assert.equal(container.querySelector(".paper-title").textContent, "A & B");
  assert.equal(container.querySelector("script, img"), null);
});

test("repairs the reported private-use bond glyph in titles and Word bibliography", () => {
  const original = "An insight into C\uf8ffH···N hydrogen bond and stability of the complexes formed by trihalomethanes with ammonia and its monohalogenated derivatives";
  const expected = original.replace("C\uf8ffH", "C-H");
  assert.equal(paperTitleText(original), expected);
  assert.equal(paperTitleText("C&#63743;H···N"), "C-H···N");
  const bibliography = dom.window.document.createElement("div");
  bibliography.innerHTML = buildBibliographyHtml("References", [original]);
  assert.equal(bibliography.querySelectorAll("p")[1].textContent, expected);
  assert.equal(paperTitleText("Apple \uf8ff / α–β / C–H / C···N"), "Apple \uf8ff / α–β / C–H / C···N");
});

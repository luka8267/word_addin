const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const { JSDOM } = require("jsdom");

const root = path.resolve(__dirname, "..");
const html = fs.readFileSync(path.join(root, "bunkenn/word-app/static/taskpane.html"), "utf8");
const source = fs.readFileSync(path.join(root, "bunkenn/word-app/static/taskpane.js"), "utf8");
const custom = {
  name: "研究室", kind: "numeric", superscript: true,
  citationTemplate: "[{number}]", bibliographyTemplate: "{number}. {title}",
};

function setup(initial = {}) {
  const dom = new JSDOM(html, { url: "https://example.test", runScripts: "outside-only" });
  let saved = structuredClone(initial);
  const calls = [];
  const controls = (initial.citations || []).map((citation) => ({
    id: citation.controlId, tag: "BUNKEN_CITATION", font: {},
    insertText(text) { this.text = text; },
    getRange() { return { font: this.font }; },
  }));
  dom.window.Office = {
    onReady() {}, AsyncResultStatus: { Succeeded: "succeeded" },
    context: { document: { settings: {
      refreshAsync(cb) { cb({ status: "succeeded" }); },
      get() { return saved; }, set(key, value) { saved = structuredClone(value); },
      saveAsync(cb) { cb({ status: "succeeded" }); },
    } } },
  };
  dom.window.Word = {
    InsertLocation: { replace: "replace" },
    run: async (fn) => fn({ load() {}, sync: async () => {}, document: { contentControls: { items: controls } } }),
  };
  dom.window.fetch = async (url, init) => {
    const payload = JSON.parse(init.body);
    calls.push({ url, payload });
    if (url.endsWith("/preview")) {
      const valid = !!payload.customStyle.name && !payload.customStyle.citationTemplate.includes("{unknown}");
      return { ok: valid, status: 400, json: async () => valid
        ? { citation: "[1]", bibliography: "1. Sample", superscript: payload.customStyle.superscript }
        : { error: "invalid template" } };
    }
    if (url.endsWith("/citations/format")) {
      return { ok: true, json: async () => ({ items: payload.items.map((item) => ({
        paperId: item.paperId, renderedText: `[${item.referenceNumber}]`,
      })) }) };
    }
    return { ok: true, json: async () => ({ entries: ["1. Sample"], title: "References" }) };
  };
  const expose = `
    collectCitationContextTexts = async function (citations) { return citations; };
    updateBibliographyFromState = async function (next) {
      next.style = getCurrentStyle();
      const numbering = await refreshCitationsForStyle(next);
      await formatBibliography(numbering.orderedPaperIds, next.style);
      await saveDocumentState(next);
    };
    globalThis.styles = { state, loadDocumentState, syncStyleSelection, getCurrentStyle,
      formatReferenceLabels, shouldSuperscriptStyle, numberBibliographyEntries,
      refreshCitationsForStyle, openStyleEditor, closeStyleEditor, saveCustomStyle,
      buildBibliographyHtml, formatBibliography, renderAuthState };
  `;
  dom.window.eval(source.replace(/\}\)\(\);\s*$/, `${expose}})();`));
  const styles = dom.window.styles;
  styles.state.isReady = true;
  styles.state.auth = { accessToken: "test" };
  styles.renderAuthState();
  return { dom, styles, calls, controls, saved: () => saved, element: (id) => dom.window.document.getElementById(id) };
}

test("new built-in styles have correct numeric labels and superscript", (t) => {
  const h = setup();
  t.after(() => h.dom.window.close());
  const s = h.styles;
  assert.equal(h.element("style-select").options.length, 12);
  assert.equal(s.formatReferenceLabels([3, 1, 2, 5], "plos"), "[1-3, 5]");
  assert.equal(s.formatReferenceLabels([1, 2, 3], "science"), "(1-3)");
  assert.equal(s.formatReferenceLabels([1, 2, 3], "american-medical-association"), "1-3");
  assert.equal(s.shouldSuperscriptStyle("american-medical-association"), true);
  assert.equal(s.shouldSuperscriptStyle("science"), false);
  assert.equal(s.shouldSuperscriptStyle("plos"), false);
  assert.deepEqual(Array.from(s.numberBibliographyEntries(["1.Alpha", "1. Beta"], "plos")), ["1. Alpha", "2. Beta"]);
  s.syncStyleSelection("american-chemical-society.csl");
  assert.equal(s.getCurrentStyle(), "american-chemical-society");
});

test("creates, persists, reopens and edits a named custom style", async (t) => {
  const h = setup();
  t.after(() => h.dom.window.close());
  await h.styles.loadDocumentState();
  h.element("new-style-button").click();
  assert.equal(h.element("style-editor").classList.contains("hidden"), false);
  h.element("style-name").value = "研究室";
  h.element("style-kind").value = "numeric";
  h.element("style-kind").dispatchEvent(new h.dom.window.Event("change"));
  h.element("style-superscript").checked = true;
  await h.styles.saveCustomStyle();
  const id = h.saved().style;
  assert.match(id, /^custom-/);
  assert.equal(h.saved().customStyles[id].name, "研究室");
  assert.equal(h.element("style-select").value, id);
  assert.equal(h.element("edit-style-button").disabled, false);
  const second = setup(h.saved());
  t.after(() => second.dom.window.close());
  const reopened = await second.styles.loadDocumentState();
  second.styles.syncStyleSelection(reopened.style);
  assert.equal(second.styles.getCurrentStyle(), id);
  assert.equal(second.styles.shouldSuperscriptStyle(id), true);
  second.element("edit-style-button").click();
  second.element("style-name").value = "研究室 改訂";
  await second.styles.saveCustomStyle();
  assert.equal(Object.keys(second.saved().customStyles).length, 1);
  assert.equal(second.saved().customStyles[id].name, "研究室 改訂");
});

test("invalid or duplicate drafts do not overwrite document settings", async (t) => {
  const initial = { style: "custom-lab", customStyles: { "custom-lab": custom } };
  const h = setup(initial);
  t.after(() => h.dom.window.close());
  await h.styles.loadDocumentState();
  h.styles.openStyleEditor("");
  h.element("style-name").value = "研究室";
  await h.styles.saveCustomStyle();
  assert.deepEqual(h.saved(), initial);
  assert.match(h.element("status").textContent, /同じ名前/);
  h.element("style-name").value = "新しい様式";
  h.element("style-citation-template").value = "{unknown}";
  await h.styles.saveCustomStyle();
  assert.deepEqual(h.saved(), initial);
  assert.match(h.element("status").textContent, /invalid template/);
});

test("custom citation requests use document-order numbers, locator and saved definition", async (t) => {
  const h = setup({ style: "custom-lab", customStyles: { "custom-lab": custom }, citations: [
    { controlId: "1", paperIds: ["b", "a"], locator: "p. 25" },
    { controlId: "2", paperIds: ["a", "c"] },
  ] });
  t.after(() => h.dom.window.close());
  const doc = await h.styles.loadDocumentState();
  const result = await h.styles.refreshCitationsForStyle(doc);
  assert.deepEqual(Array.from(result.orderedPaperIds), ["b", "a", "c"]);
  const request = h.calls.find((call) => call.url.endsWith("/citations/format"));
  assert.deepEqual(request.payload.customStyle, custom);
  assert.deepEqual(request.payload.items.map((item) => item.referenceNumber), [1, 2, 2, 3]);
  assert.equal(request.payload.items[0].locator, "p. 25");
  assert.equal(h.controls[0].text, "[1]; [2]");
  assert.equal(h.controls[0].font.superscript, true);
  await h.styles.formatBibliography(result.orderedPaperIds, doc.style);
  assert.deepEqual(h.calls.at(-1).payload.customStyle, custom);
  doc.style = "plos";
  await h.styles.refreshCitationsForStyle(doc);
  assert.equal(h.controls[0].text, "[1-2]");
  assert.equal(h.controls[0].font.superscript, false);
  assert.equal(doc.customStyles["custom-lab"].name, "研究室");
});

test("preview and saved names render markup as text", async (t) => {
  const h = setup({ customStyles: { "custom-lab": { ...custom, name: "<img src=x onerror=alert(1)>" } } });
  t.after(() => h.dom.window.close());
  await h.styles.loadDocumentState();
  assert.equal(h.element("saved-custom-styles").querySelector("img"), null);
  assert.match(h.styles.buildBibliographyHtml("References", ["<script>alert(1)</script>"]), /&lt;script&gt;/);
});

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const { JSDOM } = require("jsdom");

const root = path.resolve(__dirname, "..");
const source = fs.readFileSync(path.join(root, "bunkenn/word-app/static/taskpane.js"), "utf8");
const html = fs.readFileSync(path.join(root, "bunkenn/word-app/static/taskpane.html"), "utf8");

function createEditor() {
  const dom = new JSDOM(html, { url: "https://example.test", runScripts: "outside-only" });
  let saved = {
    wordDocumentId: "test-doc", style: "vancouver",
    citations: [
      { controlId: "1", paperIds: ["a", "b", "c", "d"], referenceNumbers: [1, 2, 3, 4], style: "vancouver", renderedText: "1-4)" },
      { controlId: "2", paperIds: ["d", "a", "c", "b"], referenceNumbers: [4, 1, 3, 2], style: "vancouver", renderedText: "1-4)", locator: "p. 25" },
    ],
  };
  let selectionId = "2";
  let parent = true;
  let containedIds = [];
  let handler;
  let pendingRefresh;
  const calls = { updates: 0, saves: 0, reads: 0 };
  const controls = ["1", "2"].map((id) => ({
    id, tag: "BUNKEN_CITATION", text: "1-4)", font: {},
    insertText(text) { this.text = text; },
    getRange() { return { font: this.font }; },
  }));
  const settings = {
    refreshAsync(callback) {
      if (pendingRefresh) pendingRefresh.push(callback);
      else callback({ status: "succeeded" });
    },
    get() { return saved; },
    set(key, value) { saved = value; },
    saveAsync(callback) { calls.saves += 1; callback({ status: "succeeded" }); },
  };
  dom.window.Office = {
    onReady() {}, AsyncResultStatus: { Succeeded: "succeeded" },
    EventType: { DocumentSelectionChanged: "selectionChanged" },
    context: { document: { settings, url: "test.docx", addHandlerAsync(event, callback, done) {
      assert.equal(event, "selectionChanged");
      handler = callback;
      done({ status: "succeeded" });
    } } },
  };
  dom.window.Word = {
    InsertLocation: { replace: "replace" },
    run: async (callback) => callback({
      load() {}, sync: async () => {}, document: {
        contentControls: { items: controls },
        getSelection() {
          calls.reads += 1;
          return {
            parentContentControlOrNullObject: { id: selectionId, tag: "BUNKEN_CITATION", isNullObject: !parent || !selectionId },
            contentControls: { items: containedIds.map((id) => ({ id, tag: "BUNKEN_CITATION" })) },
          };
        },
      },
    }),
  };
  dom.window.testCalls = calls;
  // Keep Word selection, editing, and renumbering real; replace external sync and bibliography I/O.
  const expose = `
    updateBibliographyFromState = async function (next) {
      globalThis.testCalls.updates += 1;
      await refreshCitationsForStyle(next);
      await saveDocumentState(next);
    };
    loadDocumentCitationSummary = async function () {};
    checkDocumentCitationSync = async function () {};
    collectCitationContextTexts = async function (citations) { return citations; };
    globalThis.editor = { state, setEditingCitation, loadSelectedCitationForEditing,
      removeEditingCitationPaper, registerCitationSelectionHandler, setBusy, renderAuthState };
  `;
  dom.window.eval(source.replace(/\}\)\(\);\s*$/, `${expose}})();`));
  const editor = dom.window.editor;
  editor.state.auth = { accessToken: "test" };
  editor.state.isReady = true;
  editor.state.libraryResults = ["a", "b", "c", "d"].map((id) => ({ id, title: `Paper ${id}`, authors: "", journal: "" }));
  return {
    dom, editor, calls, controls,
    saved: () => saved,
    select(id, hasParent = true, contained = []) { selectionId = id; parent = hasParent; containedIds = contained; },
    fireSelection() { handler(); },
    deferSettings() { pendingRefresh = []; },
    resolveSettings() { const callbacks = pendingRefresh; pendingRefresh = null; callbacks.forEach((callback) => callback({ status: "succeeded" })); },
    labels() { return Array.from(dom.window.document.querySelectorAll(".edit-row .citation-paper"), (node) => node.textContent); },
  };
}

test("expands a compressed citation into actual sorted reference numbers and titles without writing", async () => {
  const h = createEditor();
  await h.editor.loadSelectedCitationForEditing();
  assert.deepEqual(h.labels(), ["1) Paper a", "2) Paper b", "3) Paper c", "4) Paper d"]);
  assert.equal(h.dom.window.document.getElementById("citation-edit-panel").classList.contains("hidden"), false);
  assert.equal(h.calls.updates, 0);
  assert.equal(h.calls.saves, 0);
  h.dom.window.close();
});

test("removes the clicked sorted row, not another paper, and updates only that citation", async () => {
  const h = createEditor();
  await h.editor.loadSelectedCitationForEditing();
  const button = h.dom.window.document.querySelectorAll(".edit-row button")[2];
  assert.match(button.getAttribute("aria-label"), /3\) Paper c/);
  button.click();
  await new Promise((resolve) => setImmediate(resolve));
  const citations = h.saved().citations;
  assert.deepEqual(Array.from(citations[0].paperIds), ["a", "b", "c", "d"]);
  assert.deepEqual(Array.from(citations[1].paperIds), ["d", "a", "b"]);
  assert.equal(citations[1].locator, "p. 25");
  assert.equal(h.controls[1].text, "1)2)4)");
  assert.deepEqual(h.labels(), ["1) Paper a", "2) Paper b", "4) Paper d"]);
  assert.equal(h.calls.updates, 1);
  assert.equal(h.editor.state.libraryResults.length, 4);
  h.dom.window.close();
});

test("renumbers remaining references when removed paper has no other citation", async () => {
  const h = createEditor();
  h.saved().citations.pop();
  h.controls.pop();
  h.select("1");
  await h.editor.loadSelectedCitationForEditing();
  await h.editor.removeEditingCitationPaper(2);
  assert.deepEqual(h.labels(), ["1) Paper a", "2) Paper b", "3) Paper d"]);
  assert.equal(h.controls[0].text, "1-3)");
  h.dom.window.close();
});

test("recognizes full-control selection and rejects multiple-control selection", async () => {
  const h = createEditor();
  h.select(null, false, ["2"]);
  await h.editor.loadSelectedCitationForEditing();
  assert.equal(h.editor.state.editingCitationControlId, "2");
  h.select(null, false, ["1", "2"]);
  await h.editor.loadSelectedCitationForEditing();
  assert.equal(h.editor.state.editingCitation, null);
  h.dom.window.close();
});

test("selection-change event automatically opens editor and ignores mutation-time events", async () => {
  const h = createEditor();
  h.editor.registerCitationSelectionHandler();
  h.fireSelection();
  await new Promise((resolve) => setTimeout(resolve, 300));
  assert.equal(h.editor.state.editingCitationControlId, "2");
  assert.equal(h.calls.reads, 1);
  h.editor.setBusy(true);
  h.select("1");
  h.fireSelection();
  await new Promise((resolve) => setTimeout(resolve, 300));
  assert.equal(h.calls.reads, 1);
  assert.equal(h.editor.state.editingCitationControlId, "2");
  h.dom.window.close();
});

test("late selection reads do not overwrite the newest selection", async () => {
  const h = createEditor();
  h.deferSettings();
  const oldRead = h.editor.loadSelectedCitationForEditing({ automatic: true });
  await new Promise((resolve) => setImmediate(resolve));
  h.select(null);
  await h.editor.loadSelectedCitationForEditing({ automatic: true });
  h.resolveSettings();
  await oldRead;
  assert.equal(h.editor.state.editingCitation, null);
  h.dom.window.close();
});

test("last remaining paper cannot be removed with the per-paper action", async () => {
  const h = createEditor();
  h.saved().citations[1].paperIds = ["a"];
  h.saved().citations[1].referenceNumbers = [1];
  await h.editor.loadSelectedCitationForEditing();
  assert.equal(h.dom.window.document.querySelector(".edit-row button").disabled, true);
  await h.editor.removeEditingCitationPaper(0);
  assert.equal(h.calls.updates, 0);
  h.dom.window.close();
});

test("caret movement inside the same citation preserves an unsaved page number", async () => {
  const h = createEditor();
  await h.editor.loadSelectedCitationForEditing();
  h.dom.window.document.getElementById("locator-input").value = "p. 99";
  await h.editor.loadSelectedCitationForEditing({ automatic: true });
  assert.equal(h.dom.window.document.getElementById("locator-input").value, "p. 99");
  h.dom.window.close();
});

test("leaving a citation closes editor and losing authentication hides its contents", async () => {
  const h = createEditor();
  await h.editor.loadSelectedCitationForEditing();
  h.editor.state.auth = null;
  h.editor.renderAuthState();
  assert.equal(h.dom.window.document.getElementById("citation-edit-panel").classList.contains("hidden"), true);
  h.editor.state.auth = { accessToken: "test" };
  h.select(null);
  await h.editor.loadSelectedCitationForEditing({ automatic: true });
  assert.equal(h.editor.state.editingCitation, null);
  assert.equal(h.dom.window.document.getElementById("selection-message").textContent.includes("編集中"), false);
  h.dom.window.close();
});

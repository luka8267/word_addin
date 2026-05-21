(function () {
  const API_BASE_URL = globalThis.location.origin;
  const DOCUMENT_STATE_KEY = "bunkenDocumentState";
  const BIBLIOGRAPHY_TAG = "BUNKEN_BIBLIOGRAPHY";
  const CITATION_TAG = "BUNKEN_CITATION";
  const DOCUMENT_ID_PREFIX = "bunken_word_";
  const DEFAULT_STYLE = "vancouver";
  const SUPPORTED_STYLES = new Set(["vancouver", "apa", "acs", "nature", "ieee"]);
  const NUMERIC_STYLES = new Set(["vancouver", "acs", "nature", "ieee"]);
  const AUTH_STORAGE_KEY = "bunkenWordAuthV3";
  const LEGACY_AUTH_STORAGE_KEYS = ["bunkenWordAuth", "bunkenWordAuthV2"];

  const state = {
    isReady: false,
    isBusy: false,
    searchTimerId: null,
    selectedPaper: null,
    results: [],
    libraryResults: [],
    documentCitations: [],
    documentInfo: null,
    documentSyncIssues: [],
    editingCitationControlId: "",
    editingCitation: null,
    isLibraryOpen: false,
    hasLoadedLibrary: false,
    isDocumentCitationsOpen: false,
    hasLoadedDocumentCitations: false,
    auth: loadAuthState(),
  };

  const readyBadge = document.getElementById("ready-badge");
  const status = document.getElementById("status");
  const authCard = document.getElementById("auth-card");
  const appCard = document.getElementById("app-card");
  const searchCard = document.getElementById("search-card");
  const libraryCard = document.getElementById("library-card");
  const citationCard = document.getElementById("citation-card");
  const bibliographyCard = document.getElementById("bibliography-card");
  const documentCitationsCard = document.getElementById("document-citations-card");
  const emailInput = document.getElementById("email-input");
  const passwordInput = document.getElementById("password-input");
  const loginButton = document.getElementById("login-button");
  const logoutButton = document.getElementById("logout-button");
  const authMessage = document.getElementById("auth-message");
  const userMessage = document.getElementById("user-message");
  const searchInput = document.getElementById("search-input");
  const searchMessage = document.getElementById("search-message");
  const searchResults = document.getElementById("search-results");
  const refreshPapersButton = document.getElementById("refresh-papers-button");
  const libraryMessage = document.getElementById("library-message");
  const libraryResults = document.getElementById("library-results");
  const libraryPanel = document.getElementById("library-panel");
  const libraryToggleButton = document.getElementById("library-toggle-button");
  const styleSelect = document.getElementById("style-select");
  const locatorInput = document.getElementById("locator-input");
  const selectionMessage = document.getElementById("selection-message");
  const insertCitationButton = document.getElementById("insert-citation-button");
  const loadSelectedCitationButton = document.getElementById("load-selected-citation-button");
  const saveCitationLocatorButton = document.getElementById("save-citation-locator-button");
  const addPaperToCitationButton = document.getElementById("add-paper-to-citation-button");
  const citationEditPanel = document.getElementById("citation-edit-panel");
  const citationEditTitle = document.getElementById("citation-edit-title");
  const citationEditItems = document.getElementById("citation-edit-items");
  const deleteCitationButton = document.getElementById("delete-citation-button");
  const refreshBibliographyButton = document.getElementById("refresh-bibliography-button");
  const documentCitationsMessage = document.getElementById("document-citations-message");
  const documentCitationsPanel = document.getElementById("document-citations-panel");
  const documentCitationsToggleButton = document.getElementById("document-citations-toggle-button");
  const documentCitationsList = document.getElementById("document-citations-list");
  const refreshDocumentCitationsButton = document.getElementById("refresh-document-citations-button");
  const checkDocumentCitationsButton = document.getElementById("check-document-citations-button");
  const repairDocumentCitationsButton = document.getElementById("repair-document-citations-button");
  const documentSyncIssues = document.getElementById("document-sync-issues");

  function loadAuthState() {
    try {
      LEGACY_AUTH_STORAGE_KEYS.forEach(function (key) {
        localStorage.removeItem(key);
      });
      return JSON.parse(localStorage.getItem(AUTH_STORAGE_KEY) || "null");
    } catch (error) {
      return null;
    }
  }

  function saveAuthState(auth) {
    state.auth = auth;
    if (auth) {
      localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(auth));
    } else {
      localStorage.removeItem(AUTH_STORAGE_KEY);
    }
    renderAuthState();
  }

  function authHeaders(extraHeaders) {
    const headers = Object.assign({}, extraHeaders || {});
    if (state.auth && state.auth.accessToken) {
      headers["X-Bunken-Access-Token"] = state.auth.accessToken;
    }
    if (state.auth && state.auth.userId) {
      headers["X-Bunken-User-Id"] = state.auth.userId;
      headers["X-Bunken-Username"] = state.auth.username || "";
      headers["X-Bunken-Email"] = state.auth.email || "";
    }
    return headers;
  }

  function normalizeStyleName(style) {
    const normalized = String(style || "").trim().toLowerCase();
    return SUPPORTED_STYLES.has(normalized) ? normalized : DEFAULT_STYLE;
  }

  function getCurrentStyle() {
    return normalizeStyleName(styleSelect && styleSelect.value);
  }

  function isNumericStyle(style) {
    return NUMERIC_STYLES.has(normalizeStyleName(style));
  }

  function syncStyleSelection(style) {
    if (styleSelect) {
      styleSelect.value = normalizeStyleName(style);
    }
  }

  function setStatus(message) { status.textContent = message; }

  function formatOfficeError(error, fallbackMessage) {
    if (!error) {
      return fallbackMessage;
    }
    const parts = [];
    if (error.message) {
      parts.push(error.message);
    }
    if (error.code) {
      parts.push(`code=${error.code}`);
    }
    if (error.debugInfo && error.debugInfo.errorLocation) {
      parts.push(`location=${error.debugInfo.errorLocation}`);
    }
    return parts.length > 0 ? parts.join(" | ") : fallbackMessage;
  }

  function setReady(isReady) {
    state.isReady = isReady;
    readyBadge.textContent = isReady ? "Ready" : "Loading";
    readyBadge.classList.toggle("ready", isReady);
    updateDisabledState();
  }

  function setBusy(isBusy) {
    state.isBusy = isBusy;
    renderCitationEditPanel();
    updateDisabledState();
  }

  function renderAuthState() {
    const isAuthenticated = !!(state.auth && state.auth.accessToken);
    authCard.classList.toggle("hidden", isAuthenticated);
    appCard.classList.toggle("hidden", !isAuthenticated);
    searchCard.classList.toggle("hidden", !isAuthenticated);
    libraryCard.classList.toggle("hidden", !isAuthenticated);
    citationCard.classList.toggle("hidden", !isAuthenticated);
    bibliographyCard.classList.toggle("hidden", !isAuthenticated);
    documentCitationsCard.classList.toggle("hidden", !isAuthenticated);
    userMessage.textContent = isAuthenticated
      ? `${state.auth.username || ""}${state.auth.email ? ` (${state.auth.email})` : ""}`
      : "";
    updateDisabledState();
  }

  function updateDisabledState() {
    const authenticated = !!(state.auth && state.auth.accessToken);
    const disabled = !state.isReady || state.isBusy || !authenticated;

    emailInput.disabled = state.isBusy || !state.isReady;
    passwordInput.disabled = state.isBusy || !state.isReady;
    loginButton.disabled = state.isBusy || !state.isReady;
    logoutButton.disabled = state.isBusy || !state.isReady || !authenticated;

    searchInput.disabled = disabled;
    refreshPapersButton.disabled = !state.isReady || state.isBusy || !authenticated;
    libraryToggleButton.disabled = !state.isReady || state.isBusy || !authenticated;
    documentCitationsToggleButton.disabled = !state.isReady || state.isBusy || !authenticated;
    styleSelect.disabled = disabled;
    locatorInput.disabled = disabled;
    insertCitationButton.disabled = disabled || !state.selectedPaper;
    loadSelectedCitationButton.disabled = disabled;
    saveCitationLocatorButton.disabled = disabled || !state.editingCitationControlId;
    addPaperToCitationButton.disabled = disabled || !state.editingCitationControlId || !state.selectedPaper;
    deleteCitationButton.disabled = disabled || !state.editingCitationControlId;
    refreshBibliographyButton.disabled = disabled;
    refreshDocumentCitationsButton.disabled = disabled;
    checkDocumentCitationsButton.disabled = disabled;
    repairDocumentCitationsButton.disabled = disabled || state.documentSyncIssues.length === 0;
  }

  function addPaperIdToCitation(citation, paperId) {
    const nextPaperIds = Array.isArray(citation.paperIds)
      ? citation.paperIds.map(String)
      : [];
    const normalizedPaperId = String(paperId);
    if (!nextPaperIds.includes(normalizedPaperId)) {
      nextPaperIds.push(normalizedPaperId);
    }
    citation.paperIds = nextPaperIds;
  }

  async function insertSelectedPaperCitation(paper) {
    if (!paper) {
      setStatus("先に文献を選んでください。");
      return;
    }
    setBusy(true);
    setStatus("引用を挿入しています。");
    try {
      const documentState = await loadDocumentState();
      documentState.style = getCurrentStyle();
      await Word.run(async function (context) {
        const selection = context.document.getSelection();
        const parentControl = selection.parentContentControlOrNullObject;
        context.load(parentControl, "id,tag");
        await context.sync();

        if (!parentControl.isNullObject && parentControl.tag === CITATION_TAG) {
          const citation = documentState.citations.find(function (item) {
            return String(item.controlId) === String(parentControl.id);
          });
          if (citation) {
            addPaperIdToCitation(citation, paper.id);
            if (locatorInput.value.trim()) {
              citation.locator = locatorInput.value.trim();
            }
          }
        } else {
          const insertedRange = selection.insertText(formatReferenceLabels([(documentState.citations || []).length + 1], documentState.style), Word.InsertLocation.replace);
          const control = insertedRange.insertContentControl();
          control.tag = CITATION_TAG;
          control.title = "bunken citation";
          context.load(control, "id");
          await context.sync();

          documentState.citations.push({
            citationId: buildCitationId(),
            controlId: control.id,
            paperIds: [paper.id],
            style: documentState.style,
            locator: locatorInput.value.trim() || undefined,
            renderedText: "",
            referenceNumber: null,
            referenceNumbers: [],
          });
        }

      });
      await refreshCitationsForStyle(documentState);
      const syncResult = await saveAndSyncDocumentState(documentState);
      await loadDocumentCitationSummary(documentState);
      state.hasLoadedDocumentCitations = true;
      setStatus(
        syncResult && syncResult.synced === false
          ? `引用を挿入しました（DB同期は未完了）: ${paper.title}`
          : `引用を挿入しました: ${paper.title}`
      );
    } catch (error) {
      setStatus(formatOfficeError(error, "引用の挿入に失敗しました。"));
    } finally {
      setBusy(false);
    }
  }

  function renderPaperList(container, papers) {
    container.innerHTML = "";
    for (const paper of papers) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "paper-item";
      if (state.selectedPaper && state.selectedPaper.id === paper.id) {
        button.classList.add("selected");
      }
      button.innerHTML = `
        <strong class="paper-title"></strong>
        <span class="paper-meta"></span>
        <span class="paper-meta"></span>
      `;
      const nodes = button.querySelectorAll("strong, span");
      nodes[0].textContent = paper.title;
      nodes[1].textContent = paper.authors;
      nodes[2].textContent = formatPaperMetadataLine(paper);
      button.addEventListener("click", function () {
        state.selectedPaper = paper;
        selectionMessage.textContent = selectedPaperMessage(paper);
        renderResults();
        renderLibraryResults();
        updateDisabledState();
      });
      button.addEventListener("dblclick", function () {
        state.selectedPaper = paper;
        selectionMessage.textContent = selectedPaperMessage(paper);
        renderResults();
        renderLibraryResults();
        updateDisabledState();
        void insertSelectedPaperCitation(paper);
      });
      container.appendChild(button);
    }
  }

  function formatPaperMetadataLine(paper) {
    const parts = [];
    const publication = [];
    if (paper.journal) {
      publication.push(paper.journal);
    }
    if (paper.year) {
      publication.push(`(${paper.year})`);
    }
    if (paper.volume) {
      publication.push(paper.issue ? `${paper.volume}(${paper.issue})` : String(paper.volume));
    }
    if (paper.pages) {
      publication.push(`pp. ${paper.pages}`);
    }
    if (publication.length) {
      parts.push(publication.join(" "));
    }
    if (paper.doi) {
      parts.push(`DOI: ${paper.doi}`);
    }
    return parts.join(" / ");
  }

  function selectedPaperMessage(paper) {
    const doiPart = paper.doi ? ` / DOI: ${paper.doi}` : "";
    return `選択中: ${paper.title}${doiPart}`;
  }

  function renderResults() {
    renderPaperList(searchResults, state.results);
  }

  function renderLibraryResults() {
    renderPaperList(libraryResults, state.libraryResults);
  }

  function renderLibraryState() {
    libraryPanel.classList.toggle("hidden", !state.isLibraryOpen);
    libraryToggleButton.textContent = state.isLibraryOpen ? "一覧を閉じる" : "一覧を開く";
  }

  function renderDocumentCitationsPanelState() {
    documentCitationsPanel.classList.toggle("hidden", !state.isDocumentCitationsOpen);
    documentCitationsToggleButton.textContent = state.isDocumentCitationsOpen
      ? "引用一覧を閉じる"
      : "引用一覧を開く";
  }

  function findKnownPaper(paperId) {
    const normalizedPaperId = String(paperId || "");
    const pools = [state.results, state.libraryResults];
    for (const papers of pools) {
      const paper = (papers || []).find(function (item) {
        return String(item.id) === normalizedPaperId;
      });
      if (paper) {
        return paper;
      }
    }
    for (const citation of state.documentCitations || []) {
      for (const item of citation.items || []) {
        if (String(item.paperId) === normalizedPaperId && item.paper) {
          return item.paper;
        }
      }
    }
    return null;
  }

  function paperLabelForId(paperId) {
    const paper = findKnownPaper(paperId);
    if (!paper) {
      return String(paperId || "");
    }
    const metadata = formatPaperMetadataLine(paper);
    return metadata ? `${paper.title} / ${metadata}` : paper.title;
  }

  function clearEditingCitation() {
    state.editingCitationControlId = "";
    state.editingCitation = null;
    locatorInput.value = "";
    renderCitationEditPanel();
    updateDisabledState();
  }

  function setEditingCitation(citation) {
    state.editingCitationControlId = citation ? String(citation.controlId || "") : "";
    state.editingCitation = citation ? Object.assign({}, citation, {
      paperIds: Array.isArray(citation.paperIds) ? citation.paperIds.map(String) : [],
    }) : null;
    renderCitationEditPanel();
    updateDisabledState();
  }

  function renderCitationEditPanel() {
    citationEditItems.innerHTML = "";
    const citation = state.editingCitation;
    citationEditPanel.classList.toggle("hidden", !citation);
    if (!citation) {
      return;
    }

    citationEditTitle.textContent = `編集中: ${citation.renderedText || "引用"}`;
    (citation.paperIds || []).forEach(function (paperId, index) {
      const row = document.createElement("div");
      row.className = "edit-row";

      const label = document.createElement("span");
      label.className = "citation-paper";
      label.textContent = paperLabelForId(paperId);
      row.appendChild(label);

      const actions = document.createElement("div");
      actions.className = "edit-actions";

      const upButton = document.createElement("button");
      upButton.type = "button";
      upButton.className = "toggle-button";
      upButton.textContent = "上";
      upButton.disabled = index === 0 || state.isBusy;
      upButton.addEventListener("click", async function () {
        setBusy(true);
        setStatus("引用内の文献順序を変更しています。");
        try {
          await moveEditingCitationPaper(index, -1);
        } catch (error) {
          setStatus(error && error.message ? error.message : "文献順序を変更できませんでした。");
        } finally {
          setBusy(false);
        }
      });
      actions.appendChild(upButton);

      const downButton = document.createElement("button");
      downButton.type = "button";
      downButton.className = "toggle-button";
      downButton.textContent = "下";
      downButton.disabled = index === (citation.paperIds || []).length - 1 || state.isBusy;
      downButton.addEventListener("click", async function () {
        setBusy(true);
        setStatus("引用内の文献順序を変更しています。");
        try {
          await moveEditingCitationPaper(index, 1);
        } catch (error) {
          setStatus(error && error.message ? error.message : "文献順序を変更できませんでした。");
        } finally {
          setBusy(false);
        }
      });
      actions.appendChild(downButton);

      const removeButton = document.createElement("button");
      removeButton.type = "button";
      removeButton.className = "toggle-button";
      removeButton.textContent = "外す";
      removeButton.disabled = state.isBusy;
      removeButton.addEventListener("click", async function () {
        setBusy(true);
        setStatus("引用から文献を外しています。");
        try {
          await removeEditingCitationPaper(index);
        } catch (error) {
          setStatus(error && error.message ? error.message : "引用から文献を外せませんでした。");
        } finally {
          setBusy(false);
        }
      });
      actions.appendChild(removeButton);

      row.appendChild(actions);
      citationEditItems.appendChild(row);
    });
  }

  function renderDocumentCitations() {
    documentCitationsList.innerHTML = "";
    const citations = state.documentCitations || [];
    const updatedAt = formatDateTime(state.documentInfo && state.documentInfo.updatedAt);
    const updatedText = updatedAt ? ` 最終同期: ${updatedAt}` : "";
    if (citations.length === 0) {
      documentCitationsMessage.textContent = state.isDocumentCitationsOpen
        ? `この文書にはまだ同期済みの引用がありません。${updatedText}`
        : `この文書の引用は閉じています。${updatedText}`;
      return;
    }

    documentCitationsMessage.textContent = state.isDocumentCitationsOpen
      ? `${citations.length} 件の引用を表示しています。${updatedText}`
      : `${citations.length} 件の引用があります。${updatedText}`;
    citations.forEach(function (citation, index) {
      const item = document.createElement("button");
      item.type = "button";
      item.className = "citation-item";
      item.addEventListener("click", function () {
        void jumpToDocumentCitation(citation);
      });

      const head = document.createElement("div");
      head.className = "citation-head";
      const label = document.createElement("span");
      label.className = "citation-label";
      label.textContent = `引用 ${index + 1}`;
      const reference = document.createElement("span");
      reference.className = "citation-ref";
      reference.textContent = citation.renderedText || "";
      head.appendChild(label);
      head.appendChild(reference);
      item.appendChild(head);

      const contextSnippet = formatCitationContextSnippet(citation);
      if (contextSnippet) {
        const contextLine = document.createElement("span");
        contextLine.className = "citation-paper citation-context";
        contextLine.title = citation.contextText || "";
        contextLine.textContent = contextSnippet;
        item.appendChild(contextLine);
      }

      (citation.items || []).forEach(function (citationItem) {
        const paper = citationItem.paper || {};
        const paperLine = document.createElement("span");
        paperLine.className = "citation-paper";
        const locator = citationItem.locator ? ` ${citationItem.locator}` : "";
        const metadata = paper.title ? formatPaperMetadataLine(paper) : "";
        paperLine.textContent = paper.title
          ? `${paper.title}${locator}${metadata ? ` / ${metadata}` : ""}`
          : `${citationItem.paperId}${locator}`;
        item.appendChild(paperLine);
      });

      documentCitationsList.appendChild(item);
    });
  }

  function renderDocumentSyncIssues() {
    const issues = state.documentSyncIssues || [];
    documentSyncIssues.innerHTML = "";
    documentSyncIssues.classList.toggle("hidden", issues.length === 0);
    repairDocumentCitationsButton.classList.toggle("hidden", issues.length === 0);
    if (issues.length === 0) {
      updateDisabledState();
      return;
    }

    const summary = document.createElement("strong");
    summary.textContent = `${issues.length} 件の同期確認が必要です。`;
    documentSyncIssues.appendChild(summary);
    issues.forEach(function (issue) {
      const line = document.createElement("span");
      line.className = "sync-issue";
      line.textContent = issue.message;
      documentSyncIssues.appendChild(line);
    });
    updateDisabledState();
  }

  async function jumpToDocumentCitation(citation) {
    const controlId = String(citation && citation.controlId ? citation.controlId : "");
    if (!controlId) {
      setStatus("この引用の本文位置がまだ記録されていません。");
      return;
    }

    setBusy(true);
    setStatus("本文中の引用へ移動しています。");
    try {
      let didSelect = false;
      await Word.run(async function (context) {
        const controls = context.document.contentControls;
        context.load(controls, "items/id,items/tag");
        await context.sync();

        const control = controls.items.find(function (item) {
          return item.tag === CITATION_TAG && String(item.id) === controlId;
        });
        if (!control) {
          return;
        }
        control.select();
        didSelect = true;
        await context.sync();
      });

      if (didSelect) {
        setStatus("本文中の引用へ移動しました。");
      } else {
        setStatus("本文内で引用が見つかりません。引用一覧を更新してください。");
      }
    } catch (error) {
      setStatus(error && error.message ? error.message : "本文中の引用へ移動できませんでした。");
    } finally {
      setBusy(false);
    }
  }

  async function getCitationControlIdsInDocument() {
    const ids = [];
    await Word.run(async function (context) {
      const controls = context.document.contentControls;
      context.load(controls, "items/id,items/tag");
      await context.sync();
      controls.items.forEach(function (control) {
        if (control.tag === CITATION_TAG) {
          ids.push(String(control.id));
        }
      });
    });
    return ids;
  }

  async function getSelectedCitationControlId() {
    let selectedControlId = "";
    await Word.run(async function (context) {
      const selection = context.document.getSelection();
      const parentControl = selection.parentContentControlOrNullObject;
      context.load(parentControl, "id,tag");
      await context.sync();
      if (!parentControl.isNullObject && parentControl.tag === CITATION_TAG) {
        selectedControlId = String(parentControl.id);
      }
    });
    return selectedControlId;
  }

  async function loadSelectedCitationForEditing() {
    const controlId = await getSelectedCitationControlId();
    if (!controlId) {
      clearEditingCitation();
      setStatus("本文中の編集したい引用を選択してください。");
      return null;
    }

    const documentState = await loadDocumentState();
    const citation = (documentState.citations || []).find(function (item) {
      return String(item.controlId) === controlId;
    });
    if (!citation) {
      clearEditingCitation();
      setStatus("選択中の引用がアドイン状態に見つかりません。引用同期をチェックしてください。");
      return null;
    }

    setEditingCitation(citation);
    locatorInput.value = citation.locator || "";
    selectionMessage.textContent = `編集中: ${citation.renderedText || "引用"}`;
    setStatus("選択中の引用を読み込みました。locatorを編集して保存できます。");
    return citation;
  }

  function updateEditingCitationFromDocumentState(documentState) {
    if (!state.editingCitationControlId) {
      clearEditingCitation();
      return null;
    }
    const citation = (documentState.citations || []).find(function (item) {
      return String(item.controlId) === String(state.editingCitationControlId);
    });
    if (!citation) {
      clearEditingCitation();
      selectionMessage.textContent = "文献を選ぶと本文に引用を挿入できます。";
      return null;
    }
    setEditingCitation(citation);
    locatorInput.value = citation.locator || "";
    selectionMessage.textContent = `編集中: ${citation.renderedText || "引用"}`;
    return citation;
  }

  async function applyCitationEdit(mutator) {
    const documentState = await loadDocumentState();
    const citation = (documentState.citations || []).find(function (item) {
      return String(item.controlId) === String(state.editingCitationControlId);
    });
    if (!citation) {
      clearEditingCitation();
      throw new Error("編集中の引用が見つかりません。もう一度読み込んでください。");
    }
    const shouldContinue = mutator(citation, documentState);
    if (shouldContinue === false) {
      return { documentState, citation, changed: false };
    }
    documentState.style = getCurrentStyle();
    await updateBibliographyFromState(documentState);
    await loadDocumentCitationSummary(documentState);
    state.hasLoadedDocumentCitations = true;
    await checkDocumentCitationSync(documentState);
    return {
      documentState,
      citation: updateEditingCitationFromDocumentState(documentState),
      changed: true,
    };
  }

  async function saveSelectedCitationLocator() {
    if (!state.editingCitationControlId) {
      setStatus("先に本文中の引用を読み込んでください。");
      return;
    }

    const nextLocator = locatorInput.value.trim();
    await applyCitationEdit(function (citation) {
      if (nextLocator) {
        citation.locator = nextLocator;
      } else {
        delete citation.locator;
      }
    });
    setStatus("引用のlocatorを保存し、参考文献を更新しました。");
  }

  async function addSelectedPaperToEditingCitation() {
    if (!state.editingCitationControlId) {
      setStatus("先に本文中の引用を読み込んでください。");
      return;
    }
    if (!state.selectedPaper) {
      setStatus("追加する文献を先に選んでください。");
      return;
    }

    const result = await applyCitationEdit(function (citation) {
      const beforeCount = Array.isArray(citation.paperIds) ? citation.paperIds.length : 0;
      addPaperIdToCitation(citation, state.selectedPaper.id);
      const afterCount = Array.isArray(citation.paperIds) ? citation.paperIds.length : 0;
      if (beforeCount === afterCount) {
        return false;
      }
      return true;
    });
    if (!result.changed) {
      setStatus("この文献はすでに選択中の引用に含まれています。");
      return;
    }
    setStatus(`選択中の引用に文献を追加し、参考文献を更新しました: ${state.selectedPaper.title}`);
  }

  async function removeEditingCitationPaper(index) {
    if (!state.editingCitationControlId) {
      setStatus("先に本文中の引用を読み込んでください。");
      return;
    }
    const result = await applyCitationEdit(function (citation) {
      const paperIds = Array.isArray(citation.paperIds) ? citation.paperIds.map(String) : [];
      if (paperIds.length <= 1) {
        return false;
      }
      paperIds.splice(index, 1);
      citation.paperIds = paperIds;
      return true;
    });
    setStatus(result.changed ? "引用から文献を外し、参考文献を更新しました。" : "最後の文献は外せません。引用全体を削除してください。");
  }

  async function moveEditingCitationPaper(index, direction) {
    if (!state.editingCitationControlId) {
      setStatus("先に本文中の引用を読み込んでください。");
      return;
    }
    const result = await applyCitationEdit(function (citation) {
      const paperIds = Array.isArray(citation.paperIds) ? citation.paperIds.map(String) : [];
      const nextIndex = index + direction;
      if (nextIndex < 0 || nextIndex >= paperIds.length) {
        return false;
      }
      const [paperId] = paperIds.splice(index, 1);
      paperIds.splice(nextIndex, 0, paperId);
      citation.paperIds = paperIds;
      return true;
    });
    setStatus(result.changed ? "引用内の文献順序を変更し、参考文献を更新しました。" : "文献順序は変更されませんでした。");
  }

  async function deleteEditingCitation() {
    const controlId = String(state.editingCitationControlId || "");
    if (!controlId) {
      setStatus("先に本文中の引用を読み込んでください。");
      return;
    }

    const documentState = await loadDocumentState();
    documentState.citations = (documentState.citations || []).filter(function (citation) {
      return String(citation.controlId) !== controlId;
    });

    await Word.run(async function (context) {
      const controls = context.document.contentControls;
      context.load(controls, "items/id,items/tag");
      await context.sync();
      const control = controls.items.find(function (item) {
        return item.tag === CITATION_TAG && String(item.id) === controlId;
      });
      if (control) {
        control.delete(false);
        await context.sync();
      }
    });

    await updateBibliographyFromState(documentState);
    await loadDocumentCitationSummary(documentState);
    state.hasLoadedDocumentCitations = true;
    await checkDocumentCitationSync(documentState);
    clearEditingCitation();
    selectionMessage.textContent = "文献を選ぶと本文に引用を挿入できます。";
    setStatus("引用を削除し、参考文献を更新しました。");
  }

  async function checkDocumentCitationSync(documentState) {
    const citationControlIds = await getCitationControlIdsInDocument();
    const controls = new Set(citationControlIds);
    const stateCitations = documentState.citations || [];
    const stateControlIds = new Set(stateCitations.map(function (citation) {
      return String(citation.controlId || "");
    }).filter(Boolean));
    const stateCitationIds = new Set(stateCitations.map(function (citation) {
      return String(citation.citationId || "");
    }).filter(Boolean));
    const dbCitationIds = new Set((state.documentCitations || []).map(function (citation) {
      return String(citation.citationId || "");
    }).filter(Boolean));
    const issues = [];

    stateCitations.forEach(function (citation) {
      if (citation.controlId && !controls.has(String(citation.controlId))) {
        issues.push({
          type: "missing_word_control",
          message: `本文から削除された引用があります: ${citation.renderedText || citation.citationId}`,
        });
      }
      if (citation.citationId && !dbCitationIds.has(String(citation.citationId))) {
        issues.push({
          type: "missing_db_citation",
          message: `DBに未同期の引用があります: ${citation.renderedText || citation.citationId}`,
        });
      }
    });

    citationControlIds.forEach(function (controlId) {
      if (!stateControlIds.has(controlId)) {
        issues.push({
          type: "missing_state_citation",
          message: `本文にはありますが、アドイン状態にない引用があります: control ${controlId}`,
        });
      }
    });

    (state.documentCitations || []).forEach(function (citation) {
      if (citation.citationId && !stateCitationIds.has(String(citation.citationId))) {
        issues.push({
          type: "stale_db_citation",
          message: `DBに古い引用記録があります: ${citation.renderedText || citation.citationId}`,
        });
      } else if (citation.controlId && !controls.has(String(citation.controlId))) {
        issues.push({
          type: "db_missing_word_control",
          message: `DBの引用が本文内に見つかりません: ${citation.renderedText || citation.citationId}`,
        });
      }
    });

    state.documentSyncIssues = issues;
    renderDocumentSyncIssues();
    return issues;
  }

  async function fetchJson(url, init) {
    const requestInit = Object.assign({}, init || {});
    requestInit.headers = authHeaders(requestInit.headers);
    const response = await fetch(url, requestInit);
    if (!response.ok) {
      let detail = "";
      try {
        const payload = await response.json();
        detail = payload && payload.error ? ` - ${payload.error}` : "";
      } catch (error) {
        detail = "";
      }
      if (/bad_jwt|invalid JWT|token signature is invalid/i.test(detail)) {
        saveAuthState(null);
        state.results = [];
        state.libraryResults = [];
        state.selectedPaper = null;
        renderResults();
        renderLibraryResults();
        throw new Error("ログイン情報が古くなっています。もう一度ログインしてください。");
      }
      throw new Error(`API request failed: ${response.status}${detail}`);
    }
    return response.json();
  }

  function buildCitationId() {
    return `cit_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  }

  function buildWordDocumentId() {
    return `${DOCUMENT_ID_PREFIX}${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
  }

  function getCurrentDocumentTitle() {
    const url = Office.context && Office.context.document ? Office.context.document.url : "";
    if (!url) {
      return "Word document";
    }
    const normalized = String(url).split(/[\\/]/).filter(Boolean).pop() || "";
    return normalized || "Word document";
  }

  function formatDateTime(value) {
    if (!value) {
      return "";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return "";
    }
    return date.toLocaleString("ja-JP", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function createEmptyDocumentState() {
    return {
      version: 3,
      wordDocumentId: buildWordDocumentId(),
      documentTitle: "Word document",
      style: DEFAULT_STYLE,
      citations: [],
    };
  }

  function normalizeCitationEntry(citation) {
    if (!citation || !citation.controlId) {
      return null;
    }
    return {
      citationId: citation.citationId || buildCitationId(),
      controlId: citation.controlId,
      paperIds: Array.isArray(citation.paperIds) ? citation.paperIds.filter(Boolean).map(String) : [],
      style: normalizeStyleName(citation.style),
      locator: citation.locator || undefined,
      renderedText: citation.renderedText || "",
      contextText: citation.contextText || "",
      referenceNumber: citation.referenceNumber || null,
      referenceNumbers: Array.isArray(citation.referenceNumbers) ? citation.referenceNumbers : [],
    };
  }

  function normalizeDocumentState(value) {
    const base = Object.assign(createEmptyDocumentState(), value || {});
    base.wordDocumentId = base.wordDocumentId || buildWordDocumentId();
    base.documentTitle = base.documentTitle || getCurrentDocumentTitle();
    base.style = normalizeStyleName(base.style);
    base.citations = (base.citations || [])
      .map(normalizeCitationEntry)
      .filter(Boolean);
    return base;
  }

  function formatReferenceLabel(referenceNumber) {
    return `${referenceNumber})`;
  }

  function formatReferenceLabels(referenceNumbers, style) {
    const activeStyle = normalizeStyleName(style);
    const numbers = Array.from(new Set((referenceNumbers || []).map(Number).filter(Boolean)))
      .sort(function (left, right) { return left - right; });
    if (numbers.length === 0) {
      return "";
    }

    const ranges = [];
    let start = numbers[0];
    let end = numbers[0];
    for (let index = 1; index < numbers.length; index += 1) {
      const current = numbers[index];
      if (current === end + 1) {
        end = current;
      } else {
        ranges.push([start, end]);
        start = current;
        end = current;
      }
    }
    ranges.push([start, end]);

    return ranges.map(function (range) {
      if (activeStyle === "ieee") {
        return range[0] === range[1] ? `[${range[0]}]` : `[${range[0]}]-[${range[1]}]`;
      }
      if (activeStyle === "acs" || activeStyle === "nature") {
        return range[0] === range[1] ? `${range[0]}` : `${range[0]}-${range[1]}`;
      }
      return range[0] === range[1] ? `${range[0]})` : `${range[0]})-${range[1]})`;
    }).join(activeStyle === "ieee" ? "," : ",");
  }

  function mapCitationsByControlId(citations) {
    const byControlId = new Map();
    for (const citation of citations || []) {
      byControlId.set(String(citation.controlId), citation);
    }
    return byControlId;
  }

  function normalizeCitationContextText(text, renderedText) {
    const normalized = String(text || "").replace(/\s+/g, " ").trim();
    if (!normalized || normalized === String(renderedText || "").trim()) {
      return "";
    }
    return normalized.slice(0, 2000);
  }

  function trimCitationContextAroundMatch(text, matchText, beforeLength, afterLength) {
    const normalized = String(text || "").replace(/\s+/g, " ").trim();
    const needle = String(matchText || "").trim();
    const matchIndex = needle ? normalized.indexOf(needle) : -1;
    if (!normalized) {
      return "";
    }

    if (matchIndex < 0) {
      return normalized.length > beforeLength + afterLength
        ? `${normalized.slice(0, beforeLength + afterLength).trim()}...`
        : normalized;
    }

    const start = Math.max(0, matchIndex - beforeLength);
    const end = Math.min(normalized.length, matchIndex + needle.length + afterLength);
    const prefix = start > 0 ? "... " : "";
    const suffix = end < normalized.length ? " ..." : "";
    return `${prefix}${normalized.slice(start, end).trim()}${suffix}`;
  }

  function formatCitationContextSnippet(citation) {
    const contextText = String(citation && citation.contextText ? citation.contextText : "").trim();
    if (!contextText) {
      return "";
    }

    const candidates = citationTextCandidates(citation);
    const matchedCandidate = candidates.find(function (candidate) {
      return contextText.includes(candidate);
    });
    const snippet = trimCitationContextAroundMatch(
      contextText,
      matchedCandidate || citation.renderedText || "",
      48,
      80
    );
    return snippet ? `文脈: ${snippet}` : "";
  }

  function citationTextCandidates(citation) {
    const values = [];
    const renderedText = String(citation && citation.renderedText ? citation.renderedText : "").trim();
    if (renderedText) {
      values.push(renderedText);
      if (/^\d+(?:-\d+)?$/.test(renderedText)) {
        values.push(`${renderedText})`);
        values.push(`[${renderedText}]`);
      }
    }
    (citation && citation.referenceNumbers || []).forEach(function (number) {
      const value = String(number || "").trim();
      if (value) {
        values.push(value);
        values.push(`${value})`);
        values.push(`[${value}]`);
      }
    });
    return Array.from(new Set(values.filter(Boolean))).sort(function (left, right) {
      return right.length - left.length;
    });
  }

  function findParagraphContextForCitation(citation, paragraphTexts, startIndex) {
    const candidates = citationTextCandidates(citation);
    if (candidates.length === 0) {
      return { index: startIndex, text: "" };
    }

    for (const passStart of [startIndex, 0]) {
      for (let index = passStart; index < paragraphTexts.length; index += 1) {
        const text = paragraphTexts[index] || "";
        if (candidates.some(function (candidate) { return text.includes(candidate); })) {
          return { index, text };
        }
      }
    }
    return { index: startIndex, text: "" };
  }

  async function collectCitationContextTexts(citations) {
    const contextByControlId = new Map();
    let paragraphTexts = [];
    await Word.run(async function (context) {
      const paragraphs = context.document.body.paragraphs;
      context.load(paragraphs, "items/text");
      await context.sync();

      paragraphTexts = paragraphs.items.map(function (paragraph) {
        return paragraph.text || "";
      });

      const paragraphControlRefs = [];
      paragraphs.items.forEach(function (paragraph) {
        const controls = paragraph.getRange().contentControls;
        context.load(controls, "items/id,items/tag");
        paragraphControlRefs.push({
          paragraph,
          controls,
        });
      });
      await context.sync();

      paragraphControlRefs.forEach(function (entry) {
        (entry.controls.items || []).forEach(function (control) {
          if (control.tag === CITATION_TAG) {
            contextByControlId.set(String(control.id), entry.paragraph.text || "");
          }
        });
      });
    });

    let paragraphIndex = 0;
    return (citations || []).map(function (citation) {
      const paragraphText = contextByControlId.get(String(citation.controlId)) || "";
      const fallback = paragraphText
        ? { index: paragraphIndex, text: "" }
        : findParagraphContextForCitation(citation, paragraphTexts, paragraphIndex);
      paragraphIndex = fallback.index;
      return Object.assign({}, citation, {
        contextText: normalizeCitationContextText(
          paragraphText || fallback.text,
          citation.renderedText
        ),
      });
    });
  }

  function numberBibliographyEntries(entries) {
    return (entries || []).map(function (entry, index) {
      return `${index + 1}. ${entry}`;
    });
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function preserveSubSupHtml(value) {
    const tokens = [];
    const tokenized = String(value || "").replace(/<\/?(sub|sup)>/gi, function (tag) {
      const token = `__BUNKEN_INLINE_TAG_${tokens.length}__`;
      tokens.push(tag.toLowerCase());
      return token;
    });
    let escaped = escapeHtml(tokenized);
    tokens.forEach(function (tag, index) {
      escaped = escaped.replace(`__BUNKEN_INLINE_TAG_${index}__`, tag);
    });
    return escaped;
  }

  function buildBibliographyHtml(title, entries) {
    const entryHtml = (entries || []).map(function (entry) {
      return `<p>${preserveSubSupHtml(entry)}</p>`;
    }).join("");
    return `<p><strong>${escapeHtml(title)}</strong></p>${entryHtml || "<p></p>"}`;
  }

  function shouldSuperscriptStyle(style) {
    return ["vancouver", "acs", "nature"].includes(normalizeStyleName(style));
  }

  function applyCitationFormatting(control, referenceLabel, style) {
    control.insertText(referenceLabel, Word.InsertLocation.replace);
  }

  async function refreshCitationsForStyle(documentState) {
    const activeStyle = normalizeStyleName(documentState.style || getCurrentStyle());
    let orderedPaperIds = [];
    let nextCitations = [];

    await Word.run(async function (context) {
      const controls = context.document.contentControls;
      context.load(controls, "items/id,items/tag");
      await context.sync();

      const citationsByControlId = mapCitationsByControlId(documentState.citations);
      const controlsInOrder = controls.items.filter(function (item) { return item.tag === CITATION_TAG; });
      const seenPaperIds = new Map();

      controlsInOrder.forEach(function (control) {
        const citation = citationsByControlId.get(String(control.id));
        if (!citation || !citation.paperIds.length) {
          return;
        }
        const referenceNumbers = citation.paperIds.map(function (paperId) {
          if (!seenPaperIds.has(paperId)) {
            seenPaperIds.set(paperId, seenPaperIds.size + 1);
            orderedPaperIds.push(paperId);
          }
          return seenPaperIds.get(paperId);
        });
        nextCitations.push(Object.assign({}, citation, {
          style: activeStyle,
          referenceNumber: referenceNumbers[0] || null,
          referenceNumbers,
          renderedText: "",
        }));
      });
    });

    if (isNumericStyle(activeStyle)) {
      nextCitations = nextCitations.map(function (citation) {
        return Object.assign({}, citation, {
          renderedText: formatReferenceLabels(citation.referenceNumbers, activeStyle),
        });
      });
    } else if (nextCitations.length > 0) {
      const flatItems = [];
      nextCitations.forEach(function (citation, citationIndex) {
        citation.paperIds.forEach(function (paperId) {
          flatItems.push({
            citationIndex,
            paperId,
            locator: citation.locator,
          });
        });
      });
      const response = await formatCitation({
        style: activeStyle,
        items: flatItems.map(function (item) {
          return {
            paperId: item.paperId,
            locator: item.locator,
          };
        }),
      });
      const renderedItems = response.items || [];
      const renderedByCitation = new Map();
      renderedItems.forEach(function (item, index) {
        const source = flatItems[index];
        if (!source) {
          return;
        }
        const current = renderedByCitation.get(source.citationIndex) || [];
        current.push(item.renderedText);
        renderedByCitation.set(source.citationIndex, current);
      });
      nextCitations = nextCitations.map(function (citation, index) {
        return Object.assign({}, citation, {
          renderedText: (renderedByCitation.get(index) || []).join("; "),
        });
      });
    }

    await Word.run(async function (context) {
      const controls = context.document.contentControls;
      context.load(controls, "items/id,items/tag");
      await context.sync();

      const controlsById = new Map();
      controls.items.forEach(function (control) {
        controlsById.set(String(control.id), control);
      });
      nextCitations.forEach(function (citation) {
        const control = controlsById.get(String(citation.controlId));
        if (control) {
          applyCitationFormatting(control, citation.renderedText, activeStyle);
        }
      });
      await context.sync();
    });

    documentState.citations = nextCitations;
    documentState.citations = await collectCitationContextTexts(documentState.citations);
    documentState.documentTitle = getCurrentDocumentTitle();
    documentState.style = activeStyle;
    return {
      orderedPaperIds,
      citations: nextCitations,
    };
  }

  async function renumberDocumentCitations() {
    const documentState = await loadDocumentState();
    const numbering = await refreshCitationsForStyle(documentState);
    await saveAndSyncDocumentState(documentState);
    return {
      documentState,
      orderedPaperIds: numbering.orderedPaperIds,
    };
  }

  async function updateBibliographyFromState(documentState) {
    documentState.style = getCurrentStyle();
    const numbering = await refreshCitationsForStyle(documentState);
    const bibliography = await formatBibliography(numbering.orderedPaperIds, documentState.style);
    const numberedEntries = isNumericStyle(documentState.style)
      ? numberBibliographyEntries(bibliography.entries)
      : (bibliography.entries || []);
    const htmlContent = buildBibliographyHtml(bibliography.title, numberedEntries);

    await Word.run(async function (context) {
      const controls = context.document.contentControls;
      context.load(controls, "items/id,items/tag,items/title");
      await context.sync();

      controls.items.forEach(function (item) {
        if (item.tag === BIBLIOGRAPHY_TAG || item.title === "bunken bibliography") {
          item.delete(false);
        }
      });
      await context.sync();

      const bodyEnd = context.document.body.getRange(Word.RangeLocation.end);
      const control = bodyEnd.insertContentControl();
      control.tag = BIBLIOGRAPHY_TAG;
      control.title = "bunken bibliography";
      control.insertHtml(htmlContent, Word.InsertLocation.replace);
      context.load(control, "id");

      await context.sync();
      documentState.bibliographyControlId = control.id;
    });

    await saveAndSyncDocumentState(documentState);
    const contextCount = (documentState.citations || []).filter(function (citation) {
      return !!citation.contextText;
    }).length;
    return {
      orderedPaperIds: numbering.orderedPaperIds,
      bibliography,
      contextCount,
    };
  }

  function loadDocumentState() {
    return new Promise(function (resolve, reject) {
      Office.context.document.settings.refreshAsync(function (result) {
        if (result.status !== Office.AsyncResultStatus.Succeeded) {
          reject(new Error("document settings refresh failed"));
          return;
        }
        resolve(normalizeDocumentState(Office.context.document.settings.get(DOCUMENT_STATE_KEY)));
      });
    });
  }

  function saveDocumentState(nextState) {
    return new Promise(function (resolve, reject) {
      Office.context.document.settings.set(DOCUMENT_STATE_KEY, nextState);
      Office.context.document.settings.saveAsync(function (result) {
        if (result.status !== Office.AsyncResultStatus.Succeeded) {
          reject(new Error("document settings save failed"));
          return;
        }
        resolve();
      });
    });
  }

  function buildCitationSyncPayload(documentState) {
    return {
      wordDocumentId: documentState.wordDocumentId,
      title: documentState.documentTitle || getCurrentDocumentTitle(),
      style: normalizeStyleName(documentState.style),
      locale: "ja-JP",
      citations: (documentState.citations || []).map(function (citation, citationIndex) {
        return {
          citationId: citation.citationId,
          controlId: String(citation.controlId || ""),
          renderedText: citation.renderedText || "",
          contextText: citation.contextText || "",
          sortOrder: citationIndex + 1,
          items: (citation.paperIds || []).map(function (paperId, itemIndex) {
            return {
              paperId: String(paperId),
              locator: citation.locator || null,
              referenceNumber: Array.isArray(citation.referenceNumbers)
                ? citation.referenceNumbers[itemIndex] || null
                : citation.referenceNumber || null,
            };
          }),
        };
      }),
    };
  }

  async function syncDocumentCitations(documentState) {
    if (!(state.auth && state.auth.accessToken)) {
      return { synced: false, reason: "not_authenticated" };
    }
    return fetchJson(`${API_BASE_URL}/api/addin/documents/sync`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(buildCitationSyncPayload(documentState)),
    });
  }

  async function fetchDocumentCitations(wordDocumentId) {
    const url = new URL("/api/addin/documents/citations", API_BASE_URL);
    url.searchParams.set("wordDocumentId", wordDocumentId);
    return fetchJson(url.toString(), { method: "GET" });
  }

  async function loadDocumentCitationSummary(documentState) {
    if (!(state.auth && state.auth.accessToken)) {
      state.documentCitations = [];
      state.documentInfo = null;
      state.documentSyncIssues = [];
      renderDocumentCitations();
      renderDocumentSyncIssues();
      return;
    }
    const response = await fetchDocumentCitations(documentState.wordDocumentId);
    state.documentInfo = response.document || null;
    state.documentCitations = response.citations || [];
    renderDocumentCitations();
  }

  async function saveAndSyncDocumentState(documentState) {
    documentState.wordDocumentId = documentState.wordDocumentId || buildWordDocumentId();
    documentState.documentTitle = getCurrentDocumentTitle();
    await saveDocumentState(documentState);
    try {
      return await syncDocumentCitations(documentState);
    } catch (error) {
      console.warn("bunken document citation sync failed", error);
      return {
        synced: false,
        error: error && error.message ? error.message : "sync failed",
      };
    }
  }

  async function searchPapers(query) {
    const url = new URL("/api/addin/papers", API_BASE_URL);
    url.searchParams.set("q", query);
    const response = await fetchJson(url.toString(), {
      method: "GET",
      headers: {
        "X-Bunken-User-Id": state.auth && state.auth.userId ? state.auth.userId : "",
        "X-Bunken-Username": state.auth && state.auth.username ? state.auth.username : "",
        "X-Bunken-Email": state.auth && state.auth.email ? state.auth.email : "",
      },
    });
    return response.items || [];
  }

  async function refreshPaperViews() {
    const activeQuery = searchInput.value.trim();
    const searchPromise = activeQuery ? searchPapers(activeQuery) : Promise.resolve([]);
    const libraryPromise = state.isLibraryOpen ? searchPapers("") : Promise.resolve(state.libraryResults);
    const [searchItems, libraryItems] = await Promise.all([searchPromise, libraryPromise]);

    state.results = searchItems;
    state.libraryResults = libraryItems;
    state.hasLoadedLibrary = state.isLibraryOpen ? true : state.hasLoadedLibrary;

    searchMessage.textContent = activeQuery
      ? (searchItems.length === 0 ? "一致する文献はありません。" : `${searchItems.length} 件見つかりました。`)
      : "タイトル、著者、雑誌名で検索できます。";

    if (state.isLibraryOpen) {
      libraryMessage.textContent = libraryItems.length === 0
        ? "文献がまだありません。"
        : `${libraryItems.length} 件の文献を表示しています。`;
    }

    renderResults();
    renderLibraryResults();
  }

  async function formatCitation(payload) {
    return fetchJson(`${API_BASE_URL}/api/addin/citations/format`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Bunken-User-Id": state.auth && state.auth.userId ? state.auth.userId : "",
        "X-Bunken-Username": state.auth && state.auth.username ? state.auth.username : "",
        "X-Bunken-Email": state.auth && state.auth.email ? state.auth.email : "",
      },
      body: JSON.stringify(payload),
    });
  }

  async function formatBibliography(paperIds, style) {
    return fetchJson(`${API_BASE_URL}/api/addin/bibliography/format`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Bunken-User-Id": state.auth && state.auth.userId ? state.auth.userId : "",
        "X-Bunken-Username": state.auth && state.auth.username ? state.auth.username : "",
        "X-Bunken-Email": state.auth && state.auth.email ? state.auth.email : "",
      },
      body: JSON.stringify({ paperIds, style }),
    });
  }

  async function login(email, password) {
    return fetchJson(`${API_BASE_URL}/api/addin/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
  }

  async function loadSession() {
    return fetchJson(`${API_BASE_URL}/api/addin/auth/session`, { method: "POST" });
  }

  loginButton.addEventListener("click", async function () {
    setBusy(true);
    authMessage.textContent = "ログイン中...";
    try {
      const session = await login(emailInput.value.trim(), passwordInput.value);
      saveAuthState(session);
      const documentState = await loadDocumentState();
      await loadDocumentCitationSummary(documentState);
      passwordInput.value = "";
      authMessage.textContent = "ログインできました。";
      setStatus("bunkenn にログインしました。");
    } catch (error) {
      authMessage.textContent = error && error.message ? error.message : "ログインに失敗しました。";
      setStatus(authMessage.textContent);
    } finally {
      setBusy(false);
    }
  });

  logoutButton.addEventListener("click", function () {
    saveAuthState(null);
    state.results = [];
    state.documentCitations = [];
    state.documentInfo = null;
    state.documentSyncIssues = [];
    state.editingCitationControlId = "";
    state.editingCitation = null;
    state.selectedPaper = null;
    state.isDocumentCitationsOpen = false;
    state.hasLoadedDocumentCitations = false;
    searchInput.value = "";
    searchResults.innerHTML = "";
    renderDocumentCitationsPanelState();
    renderDocumentCitations();
    renderDocumentSyncIssues();
    authMessage.textContent = "bunkenn のアカウントでログインすると、その人の文献だけが表示されます。";
    selectionMessage.textContent = "文献を選ぶと本文に引用を挿入できます。";
    setStatus("ログアウトしました。");
  });

  searchInput.addEventListener("input", function () {
    const query = searchInput.value.trim();
    if (state.searchTimerId) { window.clearTimeout(state.searchTimerId); }
    if (!query) {
      state.results = [];
      searchMessage.textContent = "タイトル、著者、雑誌名で検索できます。";
      renderResults();
      return;
    }
    state.searchTimerId = window.setTimeout(async function () {
      setBusy(true);
      searchMessage.textContent = "検索中...";
      try {
        state.results = await searchPapers(query);
        searchMessage.textContent = state.results.length === 0
          ? "一致する文献はありません。"
          : `${state.results.length} 件見つかりました。`;
        renderResults();
      } catch (error) {
        searchMessage.textContent = formatOfficeError(error, "検索に失敗しました。");
      } finally {
        setBusy(false);
      }
    }, 350);
  });

  refreshPapersButton.addEventListener("click", async function () {
    setBusy(true);
    searchMessage.textContent = "文献を更新しています...";
    if (state.isLibraryOpen) {
      libraryMessage.textContent = "文献一覧を更新しています...";
    }
    try {
      await refreshPaperViews();
      setStatus("文献一覧を更新しました。");
    } catch (error) {
      const message = formatOfficeError(error, "文献の更新に失敗しました。");
      searchMessage.textContent = message;
      if (state.isLibraryOpen) {
        libraryMessage.textContent = message;
      }
      setStatus(message);
    } finally {
      setBusy(false);
    }
  });

  libraryToggleButton.addEventListener("click", async function () {
    state.isLibraryOpen = !state.isLibraryOpen;
    renderLibraryState();
    if (!state.isLibraryOpen || state.hasLoadedLibrary) {
      return;
    }

    setBusy(true);
    libraryMessage.textContent = "文献一覧を読み込んでいます...";
    try {
      state.libraryResults = await searchPapers("");
      state.hasLoadedLibrary = true;
      libraryMessage.textContent = state.libraryResults.length === 0
        ? "文献がまだありません。"
        : `${state.libraryResults.length} 件の文献を表示しています。`;
      renderLibraryResults();
    } catch (error) {
      libraryMessage.textContent = formatOfficeError(error, "文献一覧の読み込みに失敗しました。");
    } finally {
      setBusy(false);
    }
  });

  documentCitationsToggleButton.addEventListener("click", async function () {
    state.isDocumentCitationsOpen = !state.isDocumentCitationsOpen;
    renderDocumentCitationsPanelState();
    renderDocumentCitations();
    if (!state.isDocumentCitationsOpen || state.hasLoadedDocumentCitations) {
      return;
    }

    setBusy(true);
    documentCitationsMessage.textContent = "この文書の引用を読み込んでいます...";
    try {
      const documentState = await loadDocumentState();
      await loadDocumentCitationSummary(documentState);
      state.hasLoadedDocumentCitations = true;
    } catch (error) {
      const message = error && error.message ? error.message : "この文書の引用を読み込めませんでした。";
      documentCitationsMessage.textContent = message;
      setStatus(message);
    } finally {
      setBusy(false);
    }
  });

  insertCitationButton.addEventListener("click", async function () {
    await insertSelectedPaperCitation(state.selectedPaper);
  });

  loadSelectedCitationButton.addEventListener("click", async function () {
    setBusy(true);
    setStatus("選択中の引用を読み込んでいます。");
    try {
      await loadSelectedCitationForEditing();
    } catch (error) {
      setStatus(error && error.message ? error.message : "選択中の引用を読み込めませんでした。");
    } finally {
      setBusy(false);
    }
  });

  saveCitationLocatorButton.addEventListener("click", async function () {
    setBusy(true);
    setStatus("引用のlocatorを保存しています。");
    try {
      await saveSelectedCitationLocator();
    } catch (error) {
      setStatus(error && error.message ? error.message : "引用のlocatorを保存できませんでした。");
    } finally {
      setBusy(false);
    }
  });

  addPaperToCitationButton.addEventListener("click", async function () {
    setBusy(true);
    setStatus("選択中の引用に文献を追加しています。");
    try {
      await addSelectedPaperToEditingCitation();
    } catch (error) {
      setStatus(error && error.message ? error.message : "選択中の引用に文献を追加できませんでした。");
    } finally {
      setBusy(false);
    }
  });

  deleteCitationButton.addEventListener("click", async function () {
    setBusy(true);
    setStatus("引用を削除しています。");
    try {
      await deleteEditingCitation();
    } catch (error) {
      setStatus(error && error.message ? error.message : "引用を削除できませんでした。");
    } finally {
      setBusy(false);
    }
  });

  refreshDocumentCitationsButton.addEventListener("click", async function () {
    setBusy(true);
    documentCitationsMessage.textContent = "この文書の引用を更新しています...";
    try {
      const documentState = await loadDocumentState();
      documentState.citations = await collectCitationContextTexts(documentState.citations || []);
      const contextCount = (documentState.citations || []).filter(function (citation) {
        return !!citation.contextText;
      }).length;
      await saveAndSyncDocumentState(documentState);
      await loadDocumentCitationSummary(documentState);
      state.hasLoadedDocumentCitations = true;
      await checkDocumentCitationSync(documentState);
      setStatus(`この文書の引用一覧を更新しました。引用文同期: ${contextCount}/${(documentState.citations || []).length}件`);
    } catch (error) {
      const message = error && error.message ? error.message : "この文書の引用一覧の更新に失敗しました。";
      documentCitationsMessage.textContent = message;
      setStatus(message);
    } finally {
      setBusy(false);
    }
  });

  checkDocumentCitationsButton.addEventListener("click", async function () {
    setBusy(true);
    documentCitationsMessage.textContent = "引用の同期状態を確認しています...";
    try {
      const documentState = await loadDocumentState();
      await loadDocumentCitationSummary(documentState);
      state.hasLoadedDocumentCitations = true;
      const issues = await checkDocumentCitationSync(documentState);
      setStatus(issues.length === 0 ? "引用の同期状態は正常です。" : "引用の同期確認が必要です。");
    } catch (error) {
      const message = error && error.message ? error.message : "引用の同期チェックに失敗しました。";
      documentCitationsMessage.textContent = message;
      setStatus(message);
    } finally {
      setBusy(false);
    }
  });

  repairDocumentCitationsButton.addEventListener("click", async function () {
    setBusy(true);
    setStatus("引用同期を修復しています。");
    try {
      const documentState = await loadDocumentState();
      await refreshCitationsForStyle(documentState);
      await saveAndSyncDocumentState(documentState);
      await loadDocumentCitationSummary(documentState);
      state.hasLoadedDocumentCitations = true;
      const issues = await checkDocumentCitationSync(documentState);
      setStatus(issues.length === 0 ? "引用同期を修復しました。" : "一部の引用は手動確認が必要です。");
    } catch (error) {
      setStatus(error && error.message ? error.message : "引用同期の修復に失敗しました。");
    } finally {
      setBusy(false);
    }
  });

  styleSelect.addEventListener("change", async function () {
    setBusy(true);
    setStatus("引用スタイルを更新しています。");
    try {
      const documentState = await loadDocumentState();
      documentState.style = getCurrentStyle();
      await updateBibliographyFromState(documentState);
      await loadDocumentCitationSummary(documentState);
      state.hasLoadedDocumentCitations = true;
      setStatus("引用スタイルを更新しました。");
    } catch (error) {
      setStatus(error && error.message ? error.message : "引用スタイルの更新に失敗しました。");
    } finally {
      setBusy(false);
    }
  });

  refreshBibliographyButton.addEventListener("click", async function () {
    setBusy(true);
    setStatus("参考文献を更新しています。");
    try {
      const documentState = await loadDocumentState();
      const result = await updateBibliographyFromState(documentState);
      await loadDocumentCitationSummary(documentState);
      state.hasLoadedDocumentCitations = true;
      setStatus(`参考文献を更新しました。引用文同期: ${result.contextCount}/${(documentState.citations || []).length}件`);
    } catch (error) {
      setStatus(error && error.message ? error.message : "参考文献の更新に失敗しました。");
    } finally {
      setBusy(false);
    }
  });

  Office.onReady(async function (info) {
    if (info.host !== Office.HostType.Word) {
      setStatus("このアドインは Word 専用です。");
      return;
    }
    renderAuthState();
    renderLibraryState();
    try {
      const documentState = await loadDocumentState();
      syncStyleSelection(documentState.style);
      if (state.auth && state.auth.accessToken) {
        const session = await loadSession();
        if (session.authenticated) {
          state.auth.userId = session.userId;
          state.auth.email = session.email;
          state.auth.username = session.username;
          saveAuthState(state.auth);
          if ((documentState.citations || []).length > 0) {
            await saveAndSyncDocumentState(documentState);
          }
          setStatus("bunkenn に接続しました。");
        } else {
          saveAuthState(null);
          setStatus("ログインしてください。");
        }
      } else {
        setStatus("ログインしてください。");
      }
      setReady(true);
    } catch (error) {
      saveAuthState(null);
      setStatus(error && error.message ? error.message : "セッション確認に失敗しました。");
      setReady(true);
    }
  });
})();

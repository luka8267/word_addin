(function () {
  const API_BASE_URL = globalThis.location.origin;
  const DOCUMENT_STATE_KEY = "bunkenDocumentState";
  const BIBLIOGRAPHY_TAG = "BUNKEN_BIBLIOGRAPHY";
  const CITATION_TAG = "BUNKEN_CITATION";
  const STYLE = "vancouver";
  const AUTH_STORAGE_KEY = "bunkenWordAuth";

  const state = {
    isReady: false,
    isBusy: false,
    searchTimerId: null,
    selectedPaper: null,
    results: [],
    libraryResults: [],
    isLibraryOpen: false,
    hasLoadedLibrary: false,
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
  const emailInput = document.getElementById("email-input");
  const passwordInput = document.getElementById("password-input");
  const loginButton = document.getElementById("login-button");
  const logoutButton = document.getElementById("logout-button");
  const authMessage = document.getElementById("auth-message");
  const userMessage = document.getElementById("user-message");
  const searchInput = document.getElementById("search-input");
  const searchMessage = document.getElementById("search-message");
  const searchResults = document.getElementById("search-results");
  const libraryMessage = document.getElementById("library-message");
  const libraryResults = document.getElementById("library-results");
  const libraryPanel = document.getElementById("library-panel");
  const libraryToggleButton = document.getElementById("library-toggle-button");
  const locatorInput = document.getElementById("locator-input");
  const selectionMessage = document.getElementById("selection-message");
  const insertCitationButton = document.getElementById("insert-citation-button");
  const refreshBibliographyButton = document.getElementById("refresh-bibliography-button");

  function loadAuthState() {
    try {
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
      headers.Authorization = `Bearer ${state.auth.accessToken}`;
    }
    if (state.auth && state.auth.userId) {
      headers["X-Bunken-User-Id"] = state.auth.userId;
      headers["X-Bunken-Username"] = state.auth.username || "";
      headers["X-Bunken-Email"] = state.auth.email || "";
    }
    return headers;
  }

  function setStatus(message) { status.textContent = message; }

  function setReady(isReady) {
    state.isReady = isReady;
    readyBadge.textContent = isReady ? "Ready" : "Loading";
    readyBadge.classList.toggle("ready", isReady);
    updateDisabledState();
  }

  function setBusy(isBusy) {
    state.isBusy = isBusy;
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
    libraryToggleButton.disabled = !state.isReady || state.isBusy || !authenticated;
    locatorInput.disabled = disabled;
    insertCitationButton.disabled = disabled || !state.selectedPaper;
    refreshBibliographyButton.disabled = disabled;
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
      await Word.run(async function (context) {
        const selection = context.document.getSelection();
        const insertedRange = selection.insertText(formatReferenceLabel((documentState.citations || []).length + 1), Word.InsertLocation.replace);
        const control = insertedRange.insertContentControl();
        control.tag = CITATION_TAG;
        control.title = "bunken citation";
        control.font.superscript = true;
        context.load(control, "id");
        await context.sync();

        documentState.citations.push({
          citationId: buildCitationId(),
          controlId: control.id,
          paperIds: [paper.id],
          style: STYLE,
          locator: locatorInput.value.trim() || undefined,
          renderedText: "",
          referenceNumber: null,
        });

        await renumberCitationsInContext(context, documentState);
        await context.sync();
      });
      await saveDocumentState(documentState);
      setStatus(`引用を挿入しました: ${paper.title}`);
    } catch (error) {
      setStatus(error && error.message ? error.message : "引用の挿入に失敗しました。");
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
      nodes[2].textContent = `${paper.journal} ${paper.year ? `(${paper.year})` : ""}`;
      button.addEventListener("click", function () {
        state.selectedPaper = paper;
        selectionMessage.textContent = `選択中: ${paper.title}`;
        renderResults();
        renderLibraryResults();
        updateDisabledState();
      });
      button.addEventListener("dblclick", function () {
        state.selectedPaper = paper;
        selectionMessage.textContent = `選択中: ${paper.title}`;
        renderResults();
        renderLibraryResults();
        updateDisabledState();
        void insertSelectedPaperCitation(paper);
      });
      container.appendChild(button);
    }
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
      throw new Error(`API request failed: ${response.status}${detail}`);
    }
    return response.json();
  }

  function buildCitationId() {
    return `cit_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  }

  function createEmptyDocumentState() {
    return {
      version: 2,
      style: STYLE,
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
      style: citation.style || STYLE,
      locator: citation.locator || undefined,
      renderedText: citation.renderedText || "",
      referenceNumber: citation.referenceNumber || null,
    };
  }

  function normalizeDocumentState(value) {
    const base = Object.assign(createEmptyDocumentState(), value || {});
    base.citations = (base.citations || [])
      .map(normalizeCitationEntry)
      .filter(Boolean);
    return base;
  }

  function formatReferenceLabel(referenceNumber) {
    return `${referenceNumber})`;
  }

  function mapCitationsByControlId(citations) {
    const byControlId = new Map();
    for (const citation of citations || []) {
      byControlId.set(String(citation.controlId), citation);
    }
    return byControlId;
  }

  function numberBibliographyEntries(entries) {
    return (entries || []).map(function (entry, index) {
      return `${index + 1}. ${entry}`;
    });
  }

  function applyCitationFormatting(control, referenceLabel) {
    control.insertText(referenceLabel, Word.InsertLocation.replace);
    control.font.superscript = true;
    control.appearance = "BoundingBox";
  }

  function renumberCitationsInContext(context, documentState) {
    const controls = context.document.contentControls;
    context.load(controls, "items/id,items/tag");

    return context.sync().then(function () {
      const citationsByControlId = mapCitationsByControlId(documentState.citations);
      const controlsInOrder = controls.items.filter(function (item) { return item.tag === CITATION_TAG; });
      const seenPaperIds = new Map();
      const orderedPaperIds = [];
      const nextCitations = [];

      controlsInOrder.forEach(function (control) {
        const citation = citationsByControlId.get(String(control.id));
        if (!citation || !citation.paperIds.length) {
          return;
        }
        const primaryPaperId = citation.paperIds[0];
        if (!seenPaperIds.has(primaryPaperId)) {
          seenPaperIds.set(primaryPaperId, seenPaperIds.size + 1);
          orderedPaperIds.push(primaryPaperId);
        }
        citation.referenceNumber = seenPaperIds.get(primaryPaperId);
        citation.renderedText = formatReferenceLabel(citation.referenceNumber);
        citation.style = STYLE;
        applyCitationFormatting(control, citation.renderedText);
        nextCitations.push(citation);
      });

      documentState.citations = nextCitations;
      documentState.style = STYLE;
      return {
        orderedPaperIds,
        citations: nextCitations,
      };
    });
  }

  async function renumberDocumentCitations() {
    const documentState = await loadDocumentState();
    let orderedPaperIds = [];
    await Word.run(async function (context) {
      const numbering = await renumberCitationsInContext(context, documentState);
      orderedPaperIds = numbering.orderedPaperIds;
      await context.sync();
    });
    await saveDocumentState(documentState);
    return {
      documentState,
      orderedPaperIds,
    };
  }

  async function updateBibliographyFromState(documentState) {
    let orderedPaperIds = [];
    await Word.run(async function (context) {
      const numbering = await renumberCitationsInContext(context, documentState);
      orderedPaperIds = numbering.orderedPaperIds;
      await context.sync();
    });

    const bibliography = await formatBibliography(orderedPaperIds, STYLE);
    const numberedEntries = numberBibliographyEntries(bibliography.entries);

    await Word.run(async function (context) {
      const controls = context.document.contentControls;
      context.load(controls, "items/id,items/tag");
      await context.sync();

      const existing = controls.items.find(function (item) { return item.tag === BIBLIOGRAPHY_TAG; });
      const content = `${bibliography.title}\n\n${numberedEntries.join("\n")}`;
      if (existing) {
        existing.insertText(content, Word.InsertLocation.replace);
        documentState.bibliographyControlId = existing.id;
      } else {
        const bodyEnd = context.document.body.getRange(Word.RangeLocation.end);
        const range = bodyEnd.insertText(`\n\n${content}`, Word.InsertLocation.after);
        const control = range.insertContentControl();
        control.tag = BIBLIOGRAPHY_TAG;
        control.title = "bunken bibliography";
        context.load(control, "id");
        await context.sync();
        documentState.bibliographyControlId = control.id;
      }

      await context.sync();
    });

    documentState.style = STYLE;
    await saveDocumentState(documentState);
    return {
      orderedPaperIds,
      bibliography,
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
    state.selectedPaper = null;
    searchInput.value = "";
    searchResults.innerHTML = "";
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
        searchMessage.textContent = error && error.message ? error.message : "検索に失敗しました。";
      } finally {
        setBusy(false);
      }
    }, 350);
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
      libraryMessage.textContent = error && error.message ? error.message : "文献一覧の読み込みに失敗しました。";
    } finally {
      setBusy(false);
    }
  });

  insertCitationButton.addEventListener("click", async function () {
    await insertSelectedPaperCitation(state.selectedPaper);
  });

  refreshBibliographyButton.addEventListener("click", async function () {
    setBusy(true);
    setStatus("参考文献を更新しています。");
    try {
      const documentState = await loadDocumentState();
      await updateBibliographyFromState(documentState);
      setStatus("参考文献を更新しました。");
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
      if (state.auth && state.auth.accessToken) {
        const session = await loadSession();
        if (session.authenticated) {
          state.auth.userId = session.userId;
          state.auth.email = session.email;
          state.auth.username = session.username;
          saveAuthState(state.auth);
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

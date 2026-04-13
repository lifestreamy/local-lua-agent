const API_BASE = "http://localhost:8080";
const THEME_KEY = "localscript-web-ui-theme";
/** @deprecated миграция со старого формата */
const HISTORY_KEY = "localscript-dialog-history";
const CHATS_STATE_KEY = "localscript-chats-v1";
const MAX_HISTORY_TURNS = 8;
/** Сколько первых слов брать для автозаголовка */
const AUTO_TITLE_MAX_WORDS = 8;
const AUTO_TITLE_MAX_CHARS = 56;

const HLJS_DARK =
  "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.11.1/styles/github-dark.min.css";
const HLJS_LIGHT =
  "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.11.1/styles/github.min.css";

const promptInput = document.getElementById("prompt-input");
const contextInput = document.getElementById("context-input");
const submitBtn = document.getElementById("submit-btn");
const copyBtn = document.getElementById("copy-btn");
const codeOutput = document.getElementById("code-output");
const message = document.getElementById("message");
const spinner = document.getElementById("spinner");
const healthDot = document.getElementById("health-dot");
const healthText = document.getElementById("health-text");
const themeToggle = document.getElementById("theme-toggle");
const hljsThemeLink = document.getElementById("hljs-theme");
const useHistoryCheckbox = document.getElementById("use-history");
const clearHistoryBtn = document.getElementById("clear-history");
const newChatBtn = document.getElementById("new-chat-btn");
const chatListEl = document.getElementById("chat-list");
const chatHistoryEl = document.getElementById("chat-history");
const cancelGenerateBtn = document.getElementById("cancel-generate-btn");

/** @type {AbortController | null} */
let generateAbortController = null;

function newChatId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `chat-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function newTurnId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `turn-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function loadState() {
  try {
    const raw = localStorage.getItem(CHATS_STATE_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (!data || data.version !== 1 || !Array.isArray(data.chats)) return null;
    return data;
  } catch {
    return null;
  }
}

function saveState(state) {
  localStorage.setItem(CHATS_STATE_KEY, JSON.stringify(state));
}

/**
 * Заголовок из первых слов запроса (если своего названия нет).
 */
function titleFromFirstPrompt(text) {
  const t = (text || "").trim();
  if (!t) return "Новый чат";
  const words = t.split(/\s+/).filter(Boolean).slice(0, AUTO_TITLE_MAX_WORDS);
  let s = words.join(" ");
  if (s.length > AUTO_TITLE_MAX_CHARS) {
    s = `${s.slice(0, AUTO_TITLE_MAX_CHARS)}…`;
  }
  return s || "Чат";
}

function formatLastRequestTime(ms) {
  if (typeof ms !== "number" || !Number.isFinite(ms)) return "";
  return new Date(ms).toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function normalizeChat(chat) {
  if (typeof chat.titleIsManual !== "boolean") {
    chat.titleIsManual = false;
  }
  if (typeof chat.title !== "string") {
    chat.title = "Новый чат";
  }
  if (chat.lastRequestAt != null && typeof chat.lastRequestAt !== "number") {
    const n = Number(chat.lastRequestAt);
    chat.lastRequestAt = Number.isFinite(n) ? n : undefined;
  }
  if (
    !chat.titleIsManual &&
    Array.isArray(chat.messages) &&
    chat.messages.length > 0 &&
    chat.title === "Новый чат"
  ) {
    const first = chat.messages[0]?.prompt;
    if (first) chat.title = titleFromFirstPrompt(first);
  }
  return chat;
}

function normalizeAllChats(state) {
  state.chats.forEach(normalizeChat);
}

function migrateLegacyHistory() {
  const raw = localStorage.getItem(HISTORY_KEY);
  if (!raw) return;
  try {
    const arr = JSON.parse(raw);
    if (!Array.isArray(arr) || arr.length === 0) return;
    if (loadState()) {
      localStorage.removeItem(HISTORY_KEY);
      return;
    }
    const id = newChatId();
    const state = {
      version: 1,
      chats: [
        {
          id,
          title: "Импорт из старой версии",
          titleIsManual: true,
          updatedAt: Date.now(),
          messages: arr.slice(-MAX_HISTORY_TURNS),
          draftPrompt: "",
          draftContext: "",
          lastRequestAt: undefined,
        },
      ],
      activeId: id,
    };
    saveState(state);
    localStorage.removeItem(HISTORY_KEY);
  } catch {
    /* ignore */
  }
}

function ensureState() {
  migrateLegacyHistory();
  let state = loadState();
  if (!state || !state.chats.length) {
    const id = newChatId();
    state = {
      version: 1,
      chats: [
        {
          id,
          title: "Новый чат",
          titleIsManual: false,
          updatedAt: Date.now(),
          messages: [],
          draftPrompt: "",
          draftContext: "",
          lastRequestAt: undefined,
        },
      ],
      activeId: id,
    };
    saveState(state);
  }
  normalizeAllChats(state);
  if (!state.chats.some((c) => c.id === state.activeId)) {
    state.activeId = state.chats[0].id;
    saveState(state);
  }
  return state;
}

function getChatById(state, id) {
  return state.chats.find((c) => c.id === id) || null;
}

function getActiveChat() {
  const state = ensureState();
  return getChatById(state, state.activeId);
}

function persistActiveDrafts() {
  const state = ensureState();
  const chat = getChatById(state, state.activeId);
  if (!chat) return;
  chat.draftPrompt = promptInput.value;
  chat.draftContext = contextInput.value;
  saveState(state);
}

function applyChatToUI(chat) {
  if (!chat) return;
  promptInput.value = chat.draftPrompt || "";
  contextInput.value = chat.draftContext || "";
  renderChatHistory(chat);
  let code = null;
  for (let i = chat.messages.length - 1; i >= 0; i -= 1) {
    const m = chat.messages[i];
    if (m.pending || m.cancelled) continue;
    if (m.code) {
      code = m.code;
      break;
    }
  }
  if (code) {
    codeOutput.textContent = code;
    if (typeof hljs !== "undefined") {
      hljs.highlightElement(codeOutput);
    }
  } else {
    codeOutput.textContent = "-- Здесь появится Lua-код";
    codeOutput.className = "language-lua";
    if (typeof hljs !== "undefined") {
      hljs.highlightElement(codeOutput);
    }
  }
}

function renderChatHistory(chat) {
  if (!chatHistoryEl) return;
  chatHistoryEl.innerHTML = "";
  const turns = Array.isArray(chat?.messages) ? chat.messages : [];
  if (!turns.length) {
    const empty = document.createElement("p");
    empty.className = "history-empty";
    empty.textContent = "История пустая. Отправьте первый запрос.";
    chatHistoryEl.appendChild(empty);
    return;
  }
  for (const turn of turns) {
    const turnWrap = document.createElement("article");
    turnWrap.className = "chat-turn";

    const userRole = document.createElement("p");
    userRole.className = "chat-role";
    userRole.textContent = "Вы";
    turnWrap.appendChild(userRole);

    const prompt = document.createElement("p");
    prompt.className = "chat-prompt";
    prompt.textContent = turn.prompt || "";
    turnWrap.appendChild(prompt);

    const assistantRole = document.createElement("p");
    assistantRole.className = "chat-role";
    assistantRole.textContent = turn.pending
      ? "LocalScript (генерация...)"
      : "LocalScript";
    turnWrap.appendChild(assistantRole);

    if (turn.pending) {
      const typing = document.createElement("div");
      typing.className = "typing-indicator";
      typing.setAttribute("aria-label", "Генерация ответа");
      for (let i = 0; i < 3; i += 1) {
        const dot = document.createElement("span");
        dot.className = "typing-dot";
        typing.appendChild(dot);
      }
      turnWrap.appendChild(typing);
    } else if (turn.cancelled) {
      const cancelled = document.createElement("p");
      cancelled.className = "chat-cancelled-msg";
      cancelled.textContent = "Запрос отменён.";
      turnWrap.appendChild(cancelled);
    } else {
      const pre = document.createElement("pre");
      const code = document.createElement("code");
      code.className = "language-lua chat-answer-code";
      code.textContent = turn.code || "-- Пустой ответ";
      pre.appendChild(code);
      turnWrap.appendChild(pre);
      if (typeof hljs !== "undefined") {
        hljs.highlightElement(code);
      }
    }

    chatHistoryEl.appendChild(turnWrap);
  }
  chatHistoryEl.scrollTop = chatHistoryEl.scrollHeight;
}

function selectChat(chatId) {
  persistActiveDrafts();
  const state = ensureState();
  if (!getChatById(state, chatId)) return;
  state.activeId = chatId;
  saveState(state);
  const chat = getActiveChat();
  applyChatToUI(chat);
  renderChatList();
  setMessage("");
}

function createNewChat() {
  persistActiveDrafts();
  const state = ensureState();
  const id = newChatId();
  state.chats.unshift({
    id,
    title: "Новый чат",
    titleIsManual: false,
    updatedAt: Date.now(),
    messages: [],
    draftPrompt: "",
    draftContext: "",
    lastRequestAt: undefined,
  });
  state.activeId = id;
  saveState(state);
  applyChatToUI(getActiveChat());
  renderChatList();
  setMessage("Новый чат создан.");
}

function renameChat(chatId) {
  const state = ensureState();
  const chat = getChatById(state, chatId);
  if (!chat) return;
  normalizeChat(chat);
  const current = chat.title || "Новый чат";
  const input = window.prompt("Название чата (пусто — снова авто по первому запросу)", current);
  if (input === null) return;
  const name = input.trim();
  if (name === "") {
    chat.titleIsManual = false;
    const first = chat.messages[0]?.prompt;
    chat.title = first ? titleFromFirstPrompt(first) : "Новый чат";
  } else {
    chat.titleIsManual = true;
    chat.title = name;
  }
  saveState(state);
  renderChatList();
  setMessage(name === "" ? "Название сброшено на авто." : "Название сохранено.");
}

function deleteChat(chatId) {
  const state = ensureState();
  const idx = state.chats.findIndex((c) => c.id === chatId);
  if (idx === -1) return;
  state.chats.splice(idx, 1);
  if (!state.chats.length) {
    const id = newChatId();
    state.chats.push({
      id,
      title: "Новый чат",
      titleIsManual: false,
      updatedAt: Date.now(),
      messages: [],
      draftPrompt: "",
      draftContext: "",
      lastRequestAt: undefined,
    });
    state.activeId = id;
  } else if (state.activeId === chatId) {
    state.activeId = state.chats[0].id;
  }
  saveState(state);
  applyChatToUI(getActiveChat());
  renderChatList();
  setMessage("Чат удалён.");
}

function renderChatList() {
  const state = ensureState();
  chatListEl.innerHTML = "";
  const sorted = [...state.chats].sort((a, b) => b.updatedAt - a.updatedAt);
  for (const chat of sorted) {
    const li = document.createElement("li");
    li.className = "chat-list-item";
    if (chat.id === state.activeId) li.classList.add("active");

    const selectBtn = document.createElement("button");
    selectBtn.type = "button";
    selectBtn.className = "chat-select-btn";
    selectBtn.dataset.chatId = chat.id;

    const titleEl = document.createElement("span");
    titleEl.className = "chat-select-title";
    titleEl.textContent = chat.title || "Без названия";
    selectBtn.appendChild(titleEl);

    const timeStr = formatLastRequestTime(chat.lastRequestAt);
    if (timeStr) {
      const timeEl = document.createElement("span");
      timeEl.className = "chat-select-time";
      timeEl.textContent = `Последний запрос: ${timeStr}`;
      selectBtn.appendChild(timeEl);
    }

    const renameBtn = document.createElement("button");
    renameBtn.type = "button";
    renameBtn.className = "chat-rename-btn";
    renameBtn.setAttribute("aria-label", "Переименовать чат");
    renameBtn.textContent = "✎";
    renameBtn.dataset.renameChatId = chat.id;

    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.className = "chat-delete-btn";
    delBtn.setAttribute("aria-label", "Удалить чат");
    delBtn.textContent = "×";
    delBtn.dataset.deleteChatId = chat.id;

    li.appendChild(selectBtn);
    li.appendChild(renameBtn);
    li.appendChild(delBtn);
    chatListEl.appendChild(li);
  }
}

chatListEl.addEventListener("click", (e) => {
  const ren = e.target.closest("[data-rename-chat-id]");
  if (ren) {
    e.preventDefault();
    e.stopPropagation();
    renameChat(ren.dataset.renameChatId);
    return;
  }
  const del = e.target.closest("[data-delete-chat-id]");
  if (del) {
    e.preventDefault();
    e.stopPropagation();
    deleteChat(del.dataset.deleteChatId);
    return;
  }
  const sel = e.target.closest("[data-chat-id]");
  if (sel && sel.dataset.chatId) {
    selectChat(sel.dataset.chatId);
  }
});

function getTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  if (saved === "light" || saved === "dark") return saved;
  return "dark";
}

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem(THEME_KEY, theme);
  if (hljsThemeLink) {
    hljsThemeLink.href = theme === "light" ? HLJS_LIGHT : HLJS_DARK;
  }
  if (themeToggle) {
    themeToggle.textContent =
      theme === "dark" ? "Светлая тема" : "Тёмная тема";
  }
  const code = codeOutput?.textContent?.trim();
  if (code && typeof hljs !== "undefined") {
    hljs.highlightElement(codeOutput);
  }
}

function toggleTheme() {
  applyTheme(getTheme() === "dark" ? "light" : "dark");
}

/**
 * @param {Array<{prompt: string, code: string}>} history
 */
function buildPromptForApi(history, userPrompt, luaContext, useHistory) {
  const parts = [];

  if (useHistory && history.length > 0) {
    parts.push(
      "## История диалога (только этот чат; не смешивай с другими темами)"
    );
    history.forEach((turn, i) => {
      parts.push(`### Шаг ${i + 1}`);
      parts.push(`Запрос пользователя: ${turn.prompt}`);
      parts.push("Сгенерированный Lua:");
      parts.push(turn.code || "(пусто)");
      parts.push("---");
    });
    parts.push("");
  }

  if (luaContext) {
    parts.push("## Существующий Lua-код для доработки");
    parts.push(luaContext);
    parts.push("");
  }

  parts.push("## Текущий запрос");
  parts.push(userPrompt);

  return parts.join("\n");
}

function setLoading(isLoading) {
  spinner.classList.toggle("hidden", !isLoading);
  submitBtn.disabled = isLoading;
  cancelGenerateBtn?.classList.toggle("hidden", !isLoading);
}

function setMessage(text, isError = false) {
  message.textContent = text;
  message.classList.toggle("error", isError);
}

function setHealth(status) {
  healthDot.className = "dot";
  if (status === "ok") {
    healthDot.classList.add("dot-ok");
    healthText.textContent = "API доступно";
  } else if (status === "fail") {
    healthDot.classList.add("dot-fail");
    healthText.textContent = "API недоступно";
  } else {
    healthDot.classList.add("dot-unknown");
    healthText.textContent = "Проверка API...";
  }
}

async function checkHealth() {
  try {
    const response = await fetch(`${API_BASE}/health`);
    if (!response.ok) throw new Error();
    const data = await response.json();
    setHealth(data.status === "ok" ? "ok" : "fail");
  } catch {
    setHealth("fail");
  }
}

async function generateCode() {
  const userPrompt = promptInput.value.trim();
  const luaContext = contextInput.value.trim();
  const useHistory = useHistoryCheckbox?.checked ?? true;

  if (!userPrompt) {
    setMessage("Поле «Запрос» обязательно.", true);
    return;
  }

  const chat = getActiveChat();
  if (!chat) {
    setMessage("Нет активного чата.", true);
    return;
  }

  const historySlice = chat.messages
    .filter((m) => !m.cancelled)
    .slice(-MAX_HISTORY_TURNS);
  const prompt = buildPromptForApi(
    historySlice,
    userPrompt,
    luaContext,
    useHistory
  );
  const payload = { prompt };
  const turnId = newTurnId();

  {
    const state = ensureState();
    const c = getChatById(state, state.activeId);
    if (!c) {
      setMessage("Нет активного чата.", true);
      return;
    }
    c.messages.push({ id: turnId, prompt: userPrompt, code: "", pending: true });
    c.messages = c.messages.slice(-MAX_HISTORY_TURNS);
    const sentAt = Date.now();
    c.lastRequestAt = sentAt;
    c.updatedAt = sentAt;
    c.draftPrompt = "";
    c.draftContext = contextInput.value;
    saveState(state);
    promptInput.value = "";
    renderChatList();
    renderChatHistory(c);
  }

  generateAbortController = new AbortController();
  const { signal } = generateAbortController;

  setLoading(true);
  setMessage("Генерация кода...");

  try {
    const response = await fetch(`${API_BASE}/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal,
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Ошибка запроса к API");
    }

    const code = data.code || "";
    codeOutput.textContent = code;
    hljs.highlightElement(codeOutput);

    {
      const state = ensureState();
      const c = getChatById(state, state.activeId);
      if (c) {
        const turn = c.messages.find((m) => m.id === turnId);
        if (turn) {
          turn.code = code;
          turn.pending = false;
        }
        c.updatedAt = Date.now();
        normalizeChat(c);
        if (!c.titleIsManual && c.messages.length === 1) {
          c.title = titleFromFirstPrompt(userPrompt);
        }
        c.draftPrompt = promptInput.value;
        c.draftContext = contextInput.value;
        saveState(state);
        renderChatList();
        renderChatHistory(c);
      }
    }

    setMessage("Готово.");
  } catch (error) {
    const isAbort =
      error &&
      (error.name === "AbortError" || String(error.message || "").includes("aborted"));
    const state = ensureState();
    const c = getChatById(state, state.activeId);
    if (c) {
      const turn = c.messages.find((m) => m.id === turnId);
      if (turn) {
        turn.pending = false;
        if (isAbort) {
          turn.cancelled = true;
          turn.code = "";
        } else {
          turn.code = `-- Ошибка генерации: ${error.message}`;
        }
      }
      c.updatedAt = Date.now();
      saveState(state);
      renderChatList();
      renderChatHistory(c);
    }
    if (isAbort) {
      setMessage("Генерация отменена.");
      applyChatToUI(getActiveChat());
    } else {
      setMessage(`Ошибка: ${error.message}`, true);
    }
  } finally {
    generateAbortController = null;
    setLoading(false);
  }
}

function cancelGenerate() {
  if (generateAbortController) {
    generateAbortController.abort();
  }
}

async function copyCode() {
  const text = codeOutput.textContent || "";
  const placeholder = "-- Здесь появится Lua-код";
  if (!text.trim() || text.trim() === placeholder) {
    setMessage("Код для копирования пуст.", true);
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
    setMessage("Код скопирован.");
  } catch {
    setMessage("Не удалось скопировать код.", true);
  }
}

function clearHistory() {
  const state = ensureState();
  const chat = getChatById(state, state.activeId);
  if (!chat) return;
  normalizeChat(chat);
  chat.messages = [];
  if (!chat.titleIsManual) {
    chat.title = "Новый чат";
  }
  saveState(state);
  codeOutput.textContent = "-- Здесь появится Lua-код";
  if (typeof hljs !== "undefined") {
    hljs.highlightElement(codeOutput);
  }
  renderChatHistory(chat);
  setMessage("История этого чата очищена.");
  renderChatList();
}

promptInput.addEventListener("input", () => {
  persistActiveDrafts();
});
contextInput.addEventListener("input", () => {
  persistActiveDrafts();
});

submitBtn.addEventListener("click", generateCode);
cancelGenerateBtn?.addEventListener("click", cancelGenerate);
copyBtn.addEventListener("click", copyCode);
themeToggle?.addEventListener("click", toggleTheme);
clearHistoryBtn?.addEventListener("click", clearHistory);
newChatBtn?.addEventListener("click", createNewChat);

applyTheme(getTheme());
ensureState();
applyChatToUI(getActiveChat());
renderChatList();

setHealth("unknown");
checkHealth();
setInterval(checkHealth, 10000);

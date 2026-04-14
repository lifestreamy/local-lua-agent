"use client";

import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Loader2, Pencil, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { generateWithSseReady } from "@/lib/api";

const STORE_KEY = "localscript-next-state-v1";
const THEME_KEY = "localscript-next-theme-v1";
const STATUS_STEPS = [
  { key: "pending", label: "Ожидание" },
  { key: "generating", label: "Генерация" },
  { key: "validating", label: "Проверка" },
  { key: "retrying", label: "Повтор" },
  { key: "done", label: "Готово" },
];
const STATUS_PROGRESS_MAP = {
  pending: 8,
  generating: 35,
  validating: 70,
  retrying: 55,
  done: 100,
  error: 100,
  cancelled: 100,
};
const STATUS_LABELS = Object.fromEntries(STATUS_STEPS.map((step) => [step.key, step.label]));
const CHANNEL_LABELS = {
  sync: "Синхронный ответ /generate",
  sse: "SSE поток статусов",
  "sse + polling fallback": "SSE + fallback polling /status",
};
const ROLLING_CONTEXT_LIMIT = 4096;
const DEBUG_UI = true;

function uiDebug(event, payload = {}) {
  if (!DEBUG_UI) return;
  console.log(`[UI DEBUG] ${event}`, payload);
}

function newId(prefix) {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function nowRu(ts) {
  if (!ts) return "";
  return new Date(ts).toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function buildRollingContext(messages, maxChars = ROLLING_CONTEXT_LIMIT) {
  const turns = (messages || [])
    .filter((m) => m && m.status === "done")
    .map((m) => {
      const userPrompt = String(m.prompt || "").trim();
      const assistantText = String(m.assistantText || "").trim();
      const code = String(m.code || "").trim();

      const poisonedText = assistantText.toLowerCase().includes("запрос заблокирован системой безопасности");
      const poisonedCode = code.includes("[SECURITY_BLOCK]");
      if (poisonedText || poisonedCode) return "";

      const blocks = [];
      if (userPrompt) blocks.push(`User: ${userPrompt}`);
      if (assistantText) blocks.push(`Assistant: ${assistantText}`);
      if (code) blocks.push(`\`\`\`lua\n${code}\n\`\`\``);
      return blocks.join("\n");
    })
    .filter(Boolean);

  // Keep newest turns under hard limit by dropping oldest turns first.
  const selected = [];
  let totalLen = 0;
  for (let i = turns.length - 1; i >= 0; i -= 1) {
    const turn = turns[i];
    const sep = selected.length ? "\n" : "";
    const nextLen = totalLen + sep.length + turn.length;
    if (nextLen > maxChars) break;
    selected.push(turn);
    totalLen = nextLen;
  }

  return selected.reverse().join("\n");
}

function createChat() {
  return {
    id: newId("chat"),
    title: "Новый чат",
    titleManual: false,
    updatedAt: Date.now(),
    lastRequestAt: null,
    draftPrompt: "",
    messages: [],
  };
}

export default function Page() {
  const [state, setState] = useState(null);
  const [activeId, setActiveId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [apiStatus, setApiStatus] = useState("Проверка API...");
  const [timeline, setTimeline] = useState([]);
  const [statusChannel, setStatusChannel] = useState("sync");
  const [theme, setTheme] = useState("light");
  const [errorMsg, setErrorMsg] = useState("");
  const [abortController, setAbortController] = useState(null);
  /** Последние prompt/context, ушедшие в POST /generate (для ручной проверки). */
  const [lastWirePayload, setLastWirePayload] = useState(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed?.chats?.length) {
          setState(parsed);
          setActiveId(parsed.activeId || parsed.chats[0].id);
          return;
        }
      }
    } catch {
      // ignore corrupted local storage
    }
    const fresh = { chats: [createChat()], activeId: null };
    fresh.activeId = fresh.chats[0].id;
    setState(fresh);
    setActiveId(fresh.activeId);
    uiDebug("state:init_fresh", fresh);
  }, []);

  useEffect(() => {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === "dark" || saved === "light") {
      setTheme(saved);
      uiDebug("theme:loaded", { theme: saved });
    }
  }, []);

  useEffect(() => {
    localStorage.setItem(THEME_KEY, theme);
    uiDebug("theme:saved", { theme });
  }, [theme]);

  useEffect(() => {
    if (!state) return;
    localStorage.setItem(STORE_KEY, JSON.stringify({ ...state, activeId }));
  }, [state, activeId]);

  useEffect(() => {
    const timer = setInterval(async () => {
      try {
        const response = await fetch("http://localhost:8080/health");
        if (!response.ok) throw new Error("fail");
        setApiStatus("API доступно");
      } catch {
        setApiStatus("API недоступно");
      }
    }, 10000);
    return () => clearInterval(timer);
  }, []);

  const activeChat = useMemo(() => {
    if (!state) return null;
    return state.chats.find((c) => c.id === activeId) || state.chats[0] || null;
  }, [state, activeId]);

  const sortedChats = useMemo(() => {
    if (!state) return [];
    return [...state.chats].sort((a, b) => b.updatedAt - a.updatedAt);
  }, [state]);

  function patchActiveChat(patcher) {
    setState((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        chats: prev.chats.map((chat) =>
          chat.id === activeId ? patcher(chat) : chat
        ),
      };
    });
  }

  function patchChatById(chatId, patcher) {
    setState((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        chats: prev.chats.map((chat) => (chat.id === chatId ? patcher(chat) : chat)),
      };
    });
  }

  function pushTimelineEvent(event) {
    if (!event?.phase) return;
    setTimeline((prev) => {
      const item = {
        id: newId("evt"),
        phase: String(event.phase),
        message: String(event.message || ""),
        progress:
          typeof event.progress === "number"
            ? Math.max(0, Math.min(100, event.progress))
            : null,
      };
      const last = prev[prev.length - 1];
      if (
        last &&
        last.phase === item.phase &&
        last.message === item.message &&
        last.progress === item.progress
      ) {
        return prev;
      }
      return [...prev, item].slice(-40);
    });
  }

  function createNewChat() {
    uiDebug("chat:create_click");
    const chat = createChat();
    setState((prev) => ({ ...prev, chats: [chat, ...prev.chats] }));
    setActiveId(chat.id);
    setTimeline([]);
    setErrorMsg("");
  }

  function deleteChat(chatId) {
    uiDebug("chat:delete_click", { chatId });
    setState((prev) => {
      const chats = prev.chats.filter((c) => c.id !== chatId);
      if (!chats.length) chats.push(createChat());
      const nextActive = chats.some((c) => c.id === activeId) ? activeId : chats[0].id;
      setActiveId(nextActive);
      return { ...prev, chats };
    });
  }

  function renameChat(chat) {
    uiDebug("chat:rename_click", { chatId: chat.id, prevTitle: chat.title });
    const name = window.prompt("Название чата", chat.title || "Новый чат");
    if (name === null) return;
    patchChatById(chat.id, (c) =>
      c.id !== chat.id
        ? c
        : {
            ...c,
            title: name.trim() || "Новый чат",
            titleManual: Boolean(name.trim()),
          }
    );
  }

  async function onSubmit() {
    uiDebug("submit:click", { activeId });
    if (!activeChat) return;
    const prompt = activeChat.draftPrompt.trim();
    const context = buildRollingContext(activeChat.messages);
    uiDebug("submit:prepared", { promptLength: prompt.length, contextLength: context.length });
    if (DEBUG_UI) {
      setLastWirePayload({ at: Date.now(), prompt, context });
      uiDebug("submit:wire_payload", { prompt, context });
    }
    if (!prompt) {
      setErrorMsg("Поле «Запрос» обязательно.");
      uiDebug("submit:blocked_empty_prompt");
      return;
    }
    setErrorMsg("");
    setTimeline([]);
    setStatusChannel("sync");
    const turnId = newId("turn");
    patchActiveChat((chat) => ({
      ...chat,
      lastRequestAt: Date.now(),
      updatedAt: Date.now(),
      draftPrompt: "",
      messages: [
        ...chat.messages,
        { id: turnId, prompt, context, code: "", assistantText: "", status: "pending" },
      ],
    }));

    const controller = new AbortController();
    setAbortController(controller);
    setLoading(true);

    let finalCode = "";
    try {
      uiDebug("submit:request_started", { turnId });
      await generateWithSseReady({
        prompt,
        context,
        signal: controller.signal,
        onStatus: (status) => {
          uiDebug("status:update", { status });
          pushTimelineEvent({ phase: String(status || "").toLowerCase() });
        },
        onCodeChunk: (chunk) => {
          const piece = String(chunk || "");
          uiDebug("code:chunk", { chunkLength: piece.length });
          // Backend may send full code snapshots on multiple stages.
          if (!finalCode) {
            finalCode = piece;
          } else if (piece === finalCode || finalCode.startsWith(piece)) {
            // duplicate or shorter snapshot, keep current
          } else if (piece.startsWith(finalCode)) {
            finalCode = piece;
          } else {
            finalCode += piece;
          }
        },
        onAssistantMessage: (text) => {
          const clean = String(text || "").trim();
          if (!clean) return;
          uiDebug("assistant:message", { textLength: clean.length, text: clean });
          patchActiveChat((chat) => ({
            ...chat,
            messages: chat.messages.map((m) =>
              m.id === turnId
                ? {
                    ...m,
                    assistantText: m.assistantText
                      ? `${m.assistantText}\n\n${clean}`
                      : clean,
                  }
                : m
            ),
          }));
        },
        onTimelineEvent: (event) => {
          uiDebug("timeline:event", event || {});
          const message = String(event?.message || "").toLowerCase();
          if (message.includes("polling")) {
            setStatusChannel("sse + polling fallback");
          } else if (message.includes("task_id") || message.includes("sse")) {
            setStatusChannel("sse");
          }
          pushTimelineEvent(event);
        },
      });
      uiDebug("submit:request_success", { turnId, finalCodeLength: finalCode.length });

      patchActiveChat((chat) => {
        const messages = chat.messages.map((m) =>
          m.id === turnId ? { ...m, code: finalCode, status: "done" } : m
        );
        const title =
          !chat.titleManual && chat.messages.length === 1
            ? prompt.split(/\s+/).slice(0, 8).join(" ")
            : chat.title;
        return { ...chat, messages, title, updatedAt: Date.now() };
      });
    } catch (error) {
      uiDebug("submit:request_error", {
        turnId,
        name: error?.name,
        message: error?.message,
      });
      const isAbort = error?.name === "AbortError";
      patchActiveChat((chat) => ({
        ...chat,
        messages: chat.messages.map((m) =>
          m.id === turnId
            ? {
                ...m,
                status: isAbort ? "cancelled" : "error",
                code: isAbort ? "" : `-- Ошибка: ${error.message}`,
              }
            : m
        ),
      }));
      setErrorMsg(isAbort ? "Генерация отменена." : `Ошибка: ${error.message}`);
    } finally {
      uiDebug("submit:request_finished", { turnId });
      setLoading(false);
      setAbortController(null);
    }
  }

  if (!state || !activeChat) {
    return <div className="p-6 text-fuchsia-900">Загрузка...</div>;
  }

  const isDark = theme === "dark";
  const completedPhases = new Set(timeline.map((event) => event.phase));
  const currentPhase = timeline[timeline.length - 1]?.phase || "";
  const latestProgress = timeline[timeline.length - 1]?.progress;
  const derivedProgress =
    latestProgress ?? STATUS_PROGRESS_MAP[currentPhase] ?? (timeline.length ? 8 : 0);
  const channelLabel = CHANNEL_LABELS[statusChannel] || statusChannel;

  return (
    <div
      data-theme={theme}
      className={`min-h-screen ${
        isDark
          ? "bg-gradient-to-br from-zinc-950 via-zinc-900 to-fuchsia-950 text-fuchsia-50"
          : "bg-gradient-to-br from-rose-50 via-white to-fuchsia-100 text-fuchsia-950"
      } ${isDark ? "theme-dark" : "theme-light"}`}
    >
      <div className="mx-auto flex max-w-[1300px] gap-4 p-4">
        <Card className="w-[320px] shrink-0">
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle>Чаты</CardTitle>
            <Button size="icon" onClick={createNewChat}>
              <Plus size={16} />
            </Button>
          </CardHeader>
          <CardContent className="space-y-2">
            {sortedChats.map((chat) => (
              <div
                key={chat.id}
                onClick={() => setActiveId(chat.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setActiveId(chat.id);
                  }
                }}
                role="button"
                tabIndex={0}
                className={`w-full rounded-xl border p-3 text-left ${
                  chat.id === activeId
                    ? isDark
                      ? "border-red-500 bg-red-950/40"
                      : "border-red-400 bg-red-50"
                    : isDark
                      ? "border-fuchsia-800 bg-zinc-900 hover:bg-zinc-800"
                      : "border-fuchsia-200 bg-white hover:bg-fuchsia-50"
                }`}
              >
                <div className="truncate text-sm font-semibold">{chat.title}</div>
                {chat.lastRequestAt ? (
                  <div className={`mt-1 text-xs ${isDark ? "text-fuchsia-200/80" : "text-fuchsia-700/80"}`}>
                    Последний запрос: {nowRu(chat.lastRequestAt)}
                  </div>
                ) : null}
                <div className="mt-2 flex gap-2">
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    onClick={(e) => {
                      e.stopPropagation();
                      renameChat(chat);
                    }}
                  >
                    <Pencil size={14} />
                  </Button>
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteChat(chat.id);
                    }}
                  >
                    <Trash2 size={14} />
                  </Button>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <div className="flex min-w-0 flex-1 flex-col gap-4">
          <Card>
            <CardHeader className="flex-row items-center justify-between space-y-0">
              <CardTitle>LocalScript Next UI (SSE-ready)</CardTitle>
              <Button
                type="button"
                variant="secondary"
                onClick={() => setTheme(isDark ? "light" : "dark")}
              >
                {isDark ? "Светлая тема" : "Тёмная тема"}
              </Button>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className={`text-xs ${isDark ? "text-fuchsia-200/80" : "text-fuchsia-700/80"}`}>
                {apiStatus}
              </p>
              <p className={`text-xs ${isDark ? "text-fuchsia-300/70" : "text-fuchsia-700/70"}`}>
                Канал статусов:
                <span
                  className={`ml-1 inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ${
                    statusChannel === "sse + polling fallback"
                      ? isDark
                        ? "bg-amber-900/40 text-amber-200"
                        : "bg-amber-100 text-amber-700"
                      : statusChannel === "sse"
                        ? isDark
                          ? "bg-emerald-900/40 text-emerald-200"
                          : "bg-emerald-100 text-emerald-700"
                        : isDark
                          ? "bg-slate-800 text-slate-200"
                          : "bg-slate-100 text-slate-700"
                  }`}
                >
                  {channelLabel}
                </span>
              </p>
              <div>
                <label className="mb-1 block text-sm font-medium">Запрос</label>
                <Textarea
                  className={
                    isDark
                      ? "border-fuchsia-800 bg-zinc-900 text-fuchsia-50 placeholder:text-fuchsia-300/80"
                      : ""
                  }
                  value={activeChat.draftPrompt}
                  onChange={(e) =>
                    patchActiveChat((chat) => ({
                      ...chat,
                      draftPrompt: e.target.value,
                    }))
                  }
                  placeholder="Например: напиши функцию максимума"
                />
              </div>
              <div className="flex items-center gap-2">
                <Button onClick={onSubmit} disabled={loading}>
                  {loading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Генерация...
                    </>
                  ) : (
                    "Отправить"
                  )}
                </Button>
                {loading ? (
                  <Button
                    variant="outline"
                    onClick={() => {
                      uiDebug("submit:cancel_click");
                      abortController?.abort();
                    }}
                  >
                    Отменить
                  </Button>
                ) : null}
              </div>
              {errorMsg ? (
                <p className="text-sm text-red-600">{errorMsg}</p>
              ) : null}
            </CardContent>
          </Card>

          {DEBUG_UI && lastWirePayload ? (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Отладка: тело последнего POST /generate</CardTitle>
                <p className={`text-xs font-normal ${isDark ? "text-fuchsia-200/80" : "text-fuchsia-700/80"}`}>
                  Сравните 1-й и 2-й запрос после двух отправок. В консоли браузера смотрите фильтр{" "}
                  <code className="rounded bg-black/10 px-1">[API DEBUG] generate:wire_payload</code> — там те же
                  поля, что в <code className="rounded bg-black/10 px-1">JSON.stringify</code> у fetch.
                </p>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className={`text-xs ${isDark ? "text-fuchsia-300/80" : "text-fuchsia-700/80"}`}>
                  Время: {nowRu(lastWirePayload.at)}
                </p>
                <div>
                  <div className="mb-1 flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium">prompt</span>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs"
                      onClick={() => {
                        void navigator.clipboard?.writeText(lastWirePayload.prompt ?? "");
                      }}
                    >
                      Копировать prompt
                    </Button>
                  </div>
                  <pre
                    className={`max-h-40 overflow-auto whitespace-pre-wrap rounded-lg border p-2 text-xs ${
                      isDark ? "border-fuchsia-800 bg-zinc-950 text-fuchsia-100" : "border-fuchsia-200 bg-white"
                    }`}
                  >
                    {lastWirePayload.prompt}
                  </pre>
                </div>
                <div>
                  <div className="mb-1 flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium">context</span>
                    <span className={`text-xs ${isDark ? "text-fuchsia-300/70" : "text-fuchsia-600"}`}>
                      ({(lastWirePayload.context || "").length} симв.)
                    </span>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs"
                      onClick={() => {
                        void navigator.clipboard?.writeText(lastWirePayload.context ?? "");
                      }}
                    >
                      Копировать context
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs"
                      onClick={() => {
                        void navigator.clipboard?.writeText(
                          JSON.stringify({ prompt: lastWirePayload.prompt, context: lastWirePayload.context })
                        );
                      }}
                    >
                      Копировать JSON целиком
                    </Button>
                  </div>
                  <pre
                    className={`max-h-64 overflow-auto whitespace-pre-wrap rounded-lg border p-2 text-xs ${
                      isDark ? "border-fuchsia-800 bg-zinc-950 text-fuchsia-100" : "border-fuchsia-200 bg-white"
                    }`}
                  >
                    {lastWirePayload.context === "" ? "«пустая строка»" : lastWirePayload.context}
                  </pre>
                </div>
              </CardContent>
            </Card>
          ) : null}

          <Card>
            <CardHeader>
              <CardTitle>Этапы выполнения</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="mb-3 h-2 w-full overflow-hidden rounded-full bg-fuchsia-200/60">
                <div
                  className="h-full bg-gradient-to-r from-red-500 to-fuchsia-600 transition-all duration-300"
                  style={{ width: `${Math.max(derivedProgress, timeline.length ? 8 : 0)}%` }}
                />
              </div>
              <p className={`mb-3 text-xs ${isDark ? "text-fuchsia-200/80" : "text-fuchsia-700/80"}`}>
                Текущий этап: {currentPhase ? STATUS_LABELS[currentPhase] || currentPhase : "Ожидание запуска"}
              </p>
              <div className="flex flex-wrap gap-2">
                {STATUS_STEPS.map((step) => {
                  const active = completedPhases.has(step.key);
                  return (
                    <span
                      key={step.key}
                      className={`rounded-full px-3 py-1 text-xs font-medium ${
                        active
                          ? isDark
                            ? "bg-red-900/50 text-red-200"
                            : "bg-red-100 text-red-700"
                          : isDark
                            ? "bg-fuchsia-900/40 text-fuchsia-200/70"
                            : "bg-fuchsia-100 text-fuchsia-700/70"
                      }`}
                    >
                      {step.label}
                    </span>
                  );
                })}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Диалог</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <AnimatePresence initial={false}>
                {activeChat.messages.length === 0 ? (
                  <p className={`text-sm ${isDark ? "text-fuchsia-200/80" : "text-fuchsia-700/80"}`}>
                    История пока пустая.
                  </p>
                ) : (
                  activeChat.messages.map((m) => (
                    <motion.div
                      key={m.id}
                      initial={{ opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -12 }}
                      className={`rounded-xl border p-3 ${
                        isDark
                          ? "border-fuchsia-800 bg-zinc-900"
                          : "border-fuchsia-200 bg-white"
                      }`}
                    >
                      <p
                        className={`mb-1 text-xs font-semibold uppercase ${
                          isDark ? "text-fuchsia-300" : "text-fuchsia-700"
                        }`}
                      >
                        Вы
                      </p>
                      <p className="whitespace-pre-wrap text-sm">{m.prompt}</p>
                      <p
                        className={`mb-1 mt-3 text-xs font-semibold uppercase ${
                          isDark ? "text-fuchsia-300" : "text-fuchsia-700"
                        }`}
                      >
                        LocalScript
                      </p>
                      {m.assistantText ? (
                        <p
                          className={`mb-2 whitespace-pre-wrap text-sm ${
                            isDark ? "text-fuchsia-100" : "text-fuchsia-900"
                          }`}
                        >
                          {m.assistantText}
                        </p>
                      ) : null}
                      {m.status === "pending" ? (
                        <p className={`text-sm ${isDark ? "text-fuchsia-200" : "text-fuchsia-700"}`}>
                          Генерация...
                        </p>
                      ) : m.status === "cancelled" ? (
                        <p
                          className={`text-sm italic ${
                            isDark ? "text-fuchsia-300/80" : "text-fuchsia-700/80"
                          }`}
                        >
                          Запрос отменён.
                        </p>
                      ) : (
                        <pre
                          className={`overflow-x-auto rounded-lg p-3 text-xs ${
                            isDark
                              ? "bg-zinc-950 text-fuchsia-100"
                              : "bg-fuchsia-950 text-fuchsia-50"
                          }`}
                        >
                          <code>{m.code || "-- Пустой ответ"}</code>
                        </pre>
                      )}
                    </motion.div>
                  ))
                )}
              </AnimatePresence>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

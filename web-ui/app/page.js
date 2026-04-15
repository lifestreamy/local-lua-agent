"use client";

import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Loader2, Pencil, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { generateWithSseReady } from "@/lib/api";
import { cn } from "@/lib/utils";

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

/** Убирает CoT-блоки вида <thinking>...</thinking> из текста ответа ассистента (только клиент). */
function stripAssistantThinking(text) {
  if (!text) return "";
  return String(text)
    .replace(/<thinking>[\s\S]*?<\/thinking>/gi, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function buildRollingContext(messages, maxChars = ROLLING_CONTEXT_LIMIT) {
  const turns = (messages || [])
    .filter((m) => m && m.status === "done")
    .map((m) => {
      const userPrompt = String(m.prompt || "").trim();
      const assistantText = stripAssistantThinking(String(m.assistantText || "")).trim();
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
  const [theme, setTheme] = useState("light");
  const [errorMsg, setErrorMsg] = useState("");
  const [abortController, setAbortController] = useState(null);

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

  const resolvedActiveId = useMemo(() => {
    if (!state?.chats?.length) return null;
    if (activeId && state.chats.some((c) => c.id === activeId)) return activeId;
    return state.chats[0].id;
  }, [state, activeId]);

  const activeChat = useMemo(() => {
    if (!state || !resolvedActiveId) return null;
    return state.chats.find((c) => c.id === resolvedActiveId) || null;
  }, [state, resolvedActiveId]);

  useEffect(() => {
    if (!resolvedActiveId) return;
    if (activeId !== resolvedActiveId) {
      setActiveId(resolvedActiveId);
    }
  }, [activeId, resolvedActiveId]);

  const sortedChats = useMemo(() => {
    if (!state) return [];
    return [...state.chats].sort((a, b) => b.updatedAt - a.updatedAt);
  }, [state]);

  function patchActiveChat(patcher) {
    setState((prev) => {
      if (!prev) return prev;
      const targetId =
        prev.chats.some((chat) => chat.id === activeId) ? activeId : prev.chats[0]?.id;
      if (!targetId) return prev;
      return {
        ...prev,
        chats: prev.chats.map((chat) =>
          chat.id === targetId ? patcher(chat) : chat
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
    if (!prompt) {
      setErrorMsg("Поле «Запрос» обязательно.");
      uiDebug("submit:blocked_empty_prompt");
      return;
    }
    setErrorMsg("");
    setTimeline([]);
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
                    assistantText: stripAssistantThinking(
                      m.assistantText ? `${m.assistantText}\n\n${clean}` : clean
                    ),
                  }
                : m
            ),
          }));
        },
        onTimelineEvent: (event) => {
          uiDebug("timeline:event", event || {});
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
    return <div className="p-6 text-lg text-violet-900">Загрузка...</div>;
  }

  const isDark = theme === "dark";
  const completedPhases = new Set(timeline.map((event) => event.phase));
  const currentPhase = timeline[timeline.length - 1]?.phase || "";
  const latestProgress = timeline[timeline.length - 1]?.progress;
  const derivedProgress =
    latestProgress ?? STATUS_PROGRESS_MAP[currentPhase] ?? (timeline.length ? 8 : 0);
  return (
    <div
      data-theme={theme}
      className={`min-h-screen ${
        isDark
          ? "bg-gradient-to-br from-zinc-950 via-violet-950/35 to-zinc-950 text-zinc-200"
          : "bg-gradient-to-br from-violet-50 via-white to-red-50 text-violet-950"
      } ${isDark ? "theme-dark" : "theme-light"} text-base`}
    >
      <div className="mx-auto flex max-w-[1300px] gap-4 p-4">
        <Card className="w-[320px] shrink-0">
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle className={!isDark ? "text-violet-900" : "text-violet-200"}>Чаты</CardTitle>
            <Button size="icon" onClick={createNewChat}>
              <Plus size={18} />
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
                      ? "border-violet-500/60 bg-violet-950/40 shadow-[0_0_20px_-8px_rgba(139,92,246,0.35)]"
                      : "border-red-400 bg-red-50/90"
                    : isDark
                      ? "border-violet-900/35 bg-zinc-900/60 hover:border-violet-800/50 hover:bg-violet-950/25"
                      : "border-violet-200 bg-white hover:bg-violet-50/80"
                }`}
              >
                <div
                  className={`truncate text-base font-semibold ${!isDark ? "text-violet-950" : "text-violet-100"}`}
                >
                  {chat.title}
                </div>
                {chat.lastRequestAt ? (
                  <div className={`mt-1 text-sm ${isDark ? "text-violet-400/75" : "text-violet-700/85"}`}>
                    Последний запрос: {nowRu(chat.lastRequestAt)}
                  </div>
                ) : null}
                <div className="mt-2 flex gap-2">
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    className={
                      isDark
                        ? "text-violet-400/90 hover:bg-violet-950/50"
                        : "text-violet-600 hover:bg-violet-100"
                    }
                    onClick={(e) => {
                      e.stopPropagation();
                      renameChat(chat);
                    }}
                  >
                    <Pencil size={16} />
                  </Button>
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    className={
                      isDark
                        ? "text-violet-400/90 hover:bg-violet-950/50"
                        : "text-violet-600 hover:bg-violet-100"
                    }
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteChat(chat.id);
                    }}
                  >
                    <Trash2 size={16} />
                  </Button>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <div className="flex min-w-0 flex-1 flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle className={!isDark ? "text-violet-900" : "text-violet-100"}>
                LocalScript by @OpenTeam2026
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                <p className={`text-sm ${isDark ? "text-violet-300/85" : "text-violet-700/90"}`}>
                  {apiStatus}
                </p>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  className={cn(
                    "shrink-0",
                    !isDark && "bg-violet-100 text-violet-900 hover:bg-violet-200",
                    isDark &&
                      "border border-violet-800/60 bg-violet-950/50 text-violet-200 hover:bg-violet-900/40"
                  )}
                  onClick={() => setTheme(isDark ? "light" : "dark")}
                >
                  {isDark ? "Светлая тема" : "Тёмная тема"}
                </Button>
              </div>
              <div>
                <label
                  className={cn(
                    "mb-1 block text-base font-medium",
                    !isDark && "text-violet-800",
                    isDark && "text-violet-300"
                  )}
                >
                  Запрос
                </label>
                <Textarea
                  className={
                    isDark
                      ? "border-violet-800/50 bg-zinc-900/80 text-zinc-100 placeholder:text-white/50 focus:border-violet-500/70 focus:ring-2 focus:ring-violet-800/40"
                      : "border-violet-200 bg-white text-violet-950 placeholder:text-violet-500/75 focus:border-violet-500 focus:ring-2 focus:ring-violet-200"
                  }
                  value={activeChat.draftPrompt}
                  onChange={(e) =>
                    patchActiveChat((chat) => ({
                      ...chat,
                      draftPrompt: e.target.value,
                    }))
                  }
                  onKeyDown={(e) => {
                    if (e.key !== "Enter" || e.shiftKey) return;
                    if (e.nativeEvent.isComposing || loading) return;
                    e.preventDefault();
                    onSubmit();
                  }}
                  placeholder="Например: напиши функцию максимума"
                />
              </div>
              <div className="flex items-center gap-2">
                <Button onClick={onSubmit} disabled={loading}>
                  {loading ? (
                    <>
                      <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                      Генерация...
                    </>
                  ) : (
                    "Отправить"
                  )}
                </Button>
                {loading ? (
                  <Button
                    variant="outline"
                    className={
                      isDark
                        ? "border-violet-800/55 text-violet-200/90 hover:bg-violet-950/45 hover:text-violet-100"
                        : undefined
                    }
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
                <p className={`text-base ${isDark ? "text-red-400" : "text-red-600"}`}>{errorMsg}</p>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className={!isDark ? "text-violet-900" : "text-violet-100"}>
                Этапы выполнения
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div
                className={`mb-3 h-2 w-full overflow-hidden rounded-full ${
                  isDark ? "bg-violet-950/80" : "bg-violet-200/55"
                }`}
              >
                <div
                  className={`h-full transition-all duration-300 ${
                    isDark
                      ? "bg-gradient-to-r from-violet-600 to-fuchsia-600"
                      : "bg-gradient-to-r from-red-600 to-red-700"
                  }`}
                  style={{ width: `${Math.max(derivedProgress, timeline.length ? 8 : 0)}%` }}
                />
              </div>
              <p className={`mb-3 text-sm ${isDark ? "text-violet-300/80" : "text-violet-700/90"}`}>
                Текущий этап: {currentPhase ? STATUS_LABELS[currentPhase] || currentPhase : "Ожидание запуска"}
              </p>
              <div className="flex flex-wrap gap-2">
                {STATUS_STEPS.map((step) => {
                  const active = completedPhases.has(step.key);
                  return (
                    <span
                      key={step.key}
                      className={`rounded-full px-3.5 py-1.5 text-sm font-medium ${
                        active
                          ? isDark
                            ? "bg-violet-600/85 text-violet-50 shadow-sm shadow-violet-900/30"
                            : "bg-red-100 text-red-700"
                          : isDark
                            ? "bg-violet-950/55 text-violet-400/85"
                            : "bg-violet-100 text-violet-700/80"
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
              <CardTitle className={!isDark ? "text-violet-900" : "text-violet-100"}>Диалог</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <AnimatePresence initial={false}>
                {activeChat.messages.length === 0 ? (
                  <p className={`text-base ${isDark ? "text-violet-400/80" : "text-violet-700/90"}`}>
                    История пока пустая.
                  </p>
                ) : (
                  activeChat.messages.map((m) => {
                    const assistantVisible = stripAssistantThinking(m.assistantText);
                    return (
                    <motion.div
                      key={m.id}
                      initial={{ opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -12 }}
                      className={`rounded-xl border p-3 ${
                        isDark
                          ? "border-violet-800/35 bg-violet-950/25"
                          : "border-violet-200 bg-white"
                      }`}
                    >
                      <p
                        className={`mb-1 text-sm font-semibold uppercase ${
                          isDark ? "text-violet-400/90" : "text-violet-700"
                        }`}
                      >
                        Вы
                      </p>
                      <p
                        className={`whitespace-pre-wrap text-base ${!isDark ? "text-neutral-800" : "text-zinc-100"}`}
                      >
                        {m.prompt}
                      </p>
                      <p
                        className={`mb-1 mt-3 text-sm font-semibold uppercase ${
                          isDark ? "text-violet-400/90" : "text-violet-700"
                        }`}
                      >
                        LocalScript
                      </p>
                      {assistantVisible ? (
                        <p
                          className={`mb-2 whitespace-pre-wrap text-base ${
                            isDark ? "text-violet-200/95" : "text-violet-900"
                          }`}
                        >
                          {assistantVisible}
                        </p>
                      ) : null}
                      {m.status === "pending" ? (
                        <p className={`text-base ${isDark ? "text-violet-400/90" : "text-violet-700"}`}>
                          Генерация...
                        </p>
                      ) : m.status === "cancelled" ? (
                        <p
                          className={`text-base italic ${
                            isDark ? "text-violet-500/85" : "text-violet-600/90"
                          }`}
                        >
                          Запрос отменён.
                        </p>
                      ) : (
                        <pre
                          className={`overflow-x-auto rounded-lg border p-3 text-sm ${
                            isDark
                              ? "border-violet-800/40 bg-violet-950/50 text-violet-200"
                              : "border-rose-200/80 bg-gradient-to-br from-rose-50 to-red-50 text-red-950"
                          }`}
                        >
                          <code>{m.code || "-- Пустой ответ"}</code>
                        </pre>
                      )}
                    </motion.div>
                    );
                  })
                )}
              </AnimatePresence>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

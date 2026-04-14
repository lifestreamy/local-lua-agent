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

function createChat() {
  return {
    id: newId("chat"),
    title: "Новый чат",
    titleManual: false,
    updatedAt: Date.now(),
    lastRequestAt: null,
    draftPrompt: "",
    draftContext: "",
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
  }, []);

  useEffect(() => {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === "dark" || saved === "light") {
      setTheme(saved);
    }
  }, []);

  useEffect(() => {
    localStorage.setItem(THEME_KEY, theme);
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

  function createNewChat() {
    const chat = createChat();
    setState((prev) => ({ ...prev, chats: [chat, ...prev.chats] }));
    setActiveId(chat.id);
    setTimeline([]);
    setErrorMsg("");
  }

  function deleteChat(chatId) {
    setState((prev) => {
      const chats = prev.chats.filter((c) => c.id !== chatId);
      if (!chats.length) chats.push(createChat());
      const nextActive = chats.some((c) => c.id === activeId) ? activeId : chats[0].id;
      setActiveId(nextActive);
      return { ...prev, chats };
    });
  }

  function renameChat(chat) {
    const name = window.prompt("Название чата", chat.title || "Новый чат");
    if (name === null) return;
    patchActiveChat((c) =>
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
    if (!activeChat) return;
    const prompt = activeChat.draftPrompt.trim();
    const context = activeChat.draftContext.trim();
    if (!prompt) {
      setErrorMsg("Поле «Запрос» обязательно.");
      return;
    }
    setErrorMsg("");
    setTimeline(["pending"]);
    const turnId = newId("turn");
    patchActiveChat((chat) => ({
      ...chat,
      lastRequestAt: Date.now(),
      updatedAt: Date.now(),
      draftPrompt: "",
      messages: [
        ...chat.messages,
        { id: turnId, prompt, context, code: "", status: "pending" },
      ],
    }));

    const controller = new AbortController();
    setAbortController(controller);
    setLoading(true);

    let finalCode = "";
    try {
      await generateWithSseReady({
        prompt,
        context,
        signal: controller.signal,
        onStatus: (status) => {
          const normalized = String(status || "").toLowerCase();
          setTimeline((prev) =>
            prev.includes(normalized) ? prev : [...prev, normalized]
          );
        },
        onCodeChunk: (chunk) => {
          finalCode += chunk;
        },
      });

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
      setLoading(false);
      setAbortController(null);
    }
  }

  if (!state || !activeChat) {
    return <div className="p-6 text-fuchsia-900">Загрузка...</div>;
  }

  const isDark = theme === "dark";

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
              <button
                key={chat.id}
                type="button"
                onClick={() => setActiveId(chat.id)}
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
              </button>
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
              <div>
                <label className="mb-1 block text-sm font-medium">Контекст (Lua)</label>
                <Textarea
                  className={
                    isDark
                      ? "border-fuchsia-800 bg-zinc-900 text-fuchsia-50 placeholder:text-fuchsia-300/80"
                      : ""
                  }
                  value={activeChat.draftContext}
                  onChange={(e) =>
                    patchActiveChat((chat) => ({
                      ...chat,
                      draftContext: e.target.value,
                    }))
                  }
                  placeholder="Опционально: текущий Lua-код для доработки"
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
                    onClick={() => abortController?.abort()}
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

          <Card>
            <CardHeader>
              <CardTitle>Этапы выполнения</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {[
                  { key: "pending", label: "Ожидание" },
                  { key: "generating", label: "Генерация" },
                  { key: "validating", label: "Проверка" },
                  { key: "done", label: "Готово" },
                ].map((step) => {
                  const active = timeline.includes(step.key);
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

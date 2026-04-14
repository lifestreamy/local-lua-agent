# Prompt for Cursor (Для Алины) - V4

Скопируй этот текст и вставь в Cursor Chat или Cursor Composer (Agent Mode):

---
`@codebase` `@WEB_UI_CONTEXT_3_TIM_EDIT.md`

Мы полностью переписываем наш vanilla JS фронтенд на **Next.js (App Router)** с использованием **Tailwind CSS** и **shadcn/ui**.
**ВНИМАНИЕ: Мы ОТКАЗАЛИСЬ от WebSockets.** Мы будем использовать **Server-Sent Events (SSE) / HTTP Streaming** для получения статусов от бэкенда. Желательно использовать Vercel AI SDK (`useChat` / `useCompletion`), если это упростит стриминг.

**ПРАВИЛА БЕЗОПАСНОЙ РАЗРАБОТКИ (Git Workflow):**
Работай пошагово с микро-коммитами. Если ты в Agent Mode, выполняй команды сам. Если в Chat Mode, выведи их.

**Шаг 0: Подготовка**
- Убедись, что мы в новой ветке: `git checkout -b feat/nextjs-rewrite`
- Бэкап-коммит: `git add . && git commit -m "chore: save vanilla js state"`

**Шаг 1: Инициализация**
- Установи Next.js, Tailwind, `shadcn/ui` (и Vercel AI SDK, если нужно).
- 🛑 **ОСТАНОВКА И КОММИТ:** `git add . && git commit -m "init: Next.js and shadcn setup"`

**Шаг 2: Архитектура State (React Hooks)**
- Перепиши логику `localStorage` из старых JS файлов на React hooks.
- 🛑 **ОСТАНОВКА И КОММИТ:** `git add . && git commit -m "feat: port localStorage state to React hooks"`

**Шаг 3: API и Контракт (ВАЖНО)**
- Изучи `WEB_UI_CONTEXT_3_TIM_EDIT.md`.
- Отправляй строго **РАЗДЕЛЬНЫЕ** поля: `prompt` и `context` (Lua код). Не склеивай их!
- Подготовь мок-логику для приема SSE (timeline-статусы: Pending, Generating, Validating).
- 🛑 **ОСТАНОВКА И КОММИТ:** `git add . && git commit -m "feat: implement SSE-ready API integration with prompt/context separation"`

**Шаг 4: UI/UX и Анимации**
- Собери интерфейс чата (shadcn/ui) с плавными анимациями через Framer Motion.
- 🛑 **ОСТАНОВКА И КОММИТ:** `git add . && git commit -m "ui: build chat interface and animations"`

**Инструкция для ИИ:** Не делай всё за один проход. Делай шаг, коммит, проверяй ошибки сборки, переходи к следующему.

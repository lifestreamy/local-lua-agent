# architecture_temorary_c4

Документ фиксирует архитектуру проекта в стиле C4 (Context, Container, Component, Code) по текущему состоянию репозитория.

## C1 — System Context

### Система
`LocalScript` — локальный сервис, который преобразует текстовый запрос в Lua-код для MWS Octapi.

### Акторы и внешние системы
- **Пользователь/аналитик** — формулирует задачу на естественном языке.
- **Web UI (браузер)** — пользовательский интерфейс для чатов и отправки запросов.
- **MWS Octapi (внешняя доменная платформа)** — целевая среда выполнения Lua-скриптов.
- **Ollama runtime** — локальный LLM-сервер для генерации.

### Контекстное взаимодействие
1. Пользователь вводит запрос в UI или через API-клиент.
2. `LocalScript API` получает `prompt/context`.
3. API делегирует генерацию в Ollama.
4. API валидирует и возвращает код через SSE.
5. Полученный Lua переносится в процесс/шаг MWS Octapi.

## C2 — Containers

### Контейнер 1: `web-ui` (Next.js 16)
- Назначение: интерактивный чатовый интерфейс.
- Технологии: Next.js, React, Tailwind, framer-motion.
- Важные части:
  - `web-ui/app/page.js` — основная страница и UX-логика
  - `web-ui/lib/api.js` — API-клиент + SSE-парсер
- Внешние зависимости:
  - обращается к backend (`POST /generate`, `GET /status`, `GET /health`).

### Контейнер 2: `api` (FastAPI + Python)
- Назначение: оркестрация генерации, безопасность, валидация, SSE.
- Технологии: FastAPI, httpx, pydantic, sse-starlette.
- Публичные endpoint'ы:
  - `GET /health`
  - `POST /generate`
  - `GET /status?task_id=...`
- Внешние зависимости:
  - Ollama HTTP API (`/api/generate`, `/api/chat`)
  - `luac` бинарь для проверки синтаксиса (если `DRY_RUN=false`)

### Контейнер 3: `ollama` (LLM runtime)
- Назначение: исполнение модели `qwen2.5-coder:7b-instruct-q4_K_M`.
- Интерфейс: HTTP (`:11434`).

### Контейнер 4: `model-puller` (служебный compose-сервис)
- Назначение: гарантированная загрузка модели при старте окружения.

## C3 — Components (внутри контейнера `api`)

### `api/main.py`
- Точка входа FastAPI и lifecycle запроса.
- Хранит in-memory registry задач `TASKS`.
- Запускает фоновую задачу генерации, стримит статусы через SSE.

### `api/guard.py`
- Предфильтр безопасности промпта.
- Использует отдельный guard prompt (`prompts/system-prompt-guard.txt`).
- Блокирует инъекции/оффтоп, возвращает `SECURITY_BLOCK` fallback.

### `api/agent.py` (`AgentPipeline`)
- Сердце генерационного пайплайна.
- Шаги:
  1. собрать промпт (`PromptBuilder`)
  2. вызвать Ollama
  3. извлечь код из ответа
  4. проверить `luac`
  5. повторить до `MAX_RETRIES` при синтаксической ошибке
- Возвращает структурированные `stage/message/code/error`.

### `api/prompt_builder.py`
- Сборка финального промпта:
  - системный prompt
  - optional context
  - optional error context от прошлой попытки
  - текущий user prompt

### `api/validator.py`
- Локальный валидатор синтаксиса Lua.
- Команда: `luac -o /dev/null -`.
- При `DRY_RUN=true` возвращает успех без запуска `luac`.

### `api/models.py`
- Контрактные DTO для API:
  - `GenerateRequest`
  - `TaskSubmitResponse`
  - `TaskStatusEvent`

## C3 — Components (внутри контейнера `web-ui`)

### `app/page.js`
- Основной orchestrator UI-состояния:
  - список чатов
  - ввод запроса
  - отправка
  - таймлайн статусов
  - отображение кода/сообщений
- Формирует rolling context из истории сообщений.
- Фильтрует служебные и нежелательные фрагменты в контексте.

### `lib/api.js`
- Транспортный слой для frontend:
  - `generateWithSseReady(...)`
  - обработка JSON/SSE-веток ответа
  - нормализация фаз статусов
  - парсинг SSE чанков

### `components/ui/*`
- Примитивы интерфейса (`button`, `card`, `input`, `textarea`), стилистическое оформление.

## C4 — Code-level View (критические последовательности)

### Sequence A: генерация кода (happy path)
1. UI вызывает `generateWithSseReady(prompt, context)`.
2. `POST /generate` возвращает `task_id`.
3. UI открывает SSE к `GET /status`.
4. `main.py` запускает `run_pipeline_task`.
5. `guard.py` проверяет безопасность prompt/context.
6. `agent.py` генерирует код через Ollama.
7. `validator.py` проверяет синтаксис `luac`.
8. В SSE отправляется `stage=done` с финальным `code`.
9. UI обновляет чат и показывает результат.

### Sequence B: ошибка синтаксиса и retry
1. `agent.py` получает невалидный Lua.
2. `validator.py` возвращает stderr `luac`.
3. `agent.py` публикует `stage=retrying`.
4. `prompt_builder.py` добавляет `error_context`.
5. Новая попытка генерации до `MAX_RETRIES`.

### Sequence C: security block
1. Guard классифицирует prompt как unsafe.
2. `main.py` не запускает генерационный pipeline.
3. В SSE отправляется `done` + `SECURITY_BLOCK` код.
4. UI помечает результат как завершенный с блокировкой.

## Нефункциональные аспекты

- **State management:** `TASKS` в памяти процесса (без Redis/БД).
- **Streaming:** SSE вместо WebSocket.
- **Resilience:** retry-loop на уровне генерации и валидации.
- **Security:** отдельный guard-проход + post-sanitize output.
- **Portability:** режим `DRY_RUN` для Windows без `luac`.

## Риски и ограничения архитектуры

- In-memory `TASKS` не переживает рестарт процесса.
- Нет горизонтального shared-state для нескольких API-инстансов.
- Качество и латентность сильно зависят от доступности Ollama/GPU.
- Слабая изоляция от регрессий контракта без строгой схемы event types в SSE.

## Связанные документы

- `docs/api_contract_description.md`
- `docs/CLIENT_CONTEXT_CONTRACT.md`
- `docs/architecture/C1.md`
- `docs/architecture/C2.md`
- `docs/architecture/C3.md`

# LocalScript

## Содержание

1. [Заголовок и краткое описание](#readme-1)
2. [Быстрый запуск](#readme-2)
3. [Структура проекта](#readme-3)
4. [Клиенты](#readme-4)
5. [API (асинхронная модель)](#readme-5)
6. [Архитектурные контракты](#readme-6)
7. [Ручной запуск (Ollama + uvicorn, без Docker)](#readme-7)

<a id="readme-1"></a>
## 1. Заголовок и краткое описание

**True Tech Hack 2026** · локальный ИИ-ассистент для генерации и проверки Lua-скриптов под **MWS Octapi LowCode**. Модель **Qwen2.5-Coder 7B** (Ollama) формирует код; целевая среда исполнения — **Lua 5.5** на стороне MWS; на стороне сервиса синтаксис проверяется компилятором **`luac`**. Обмен с клиентами — **асинхронно** (`task_id` + **SSE**). Облачные LLM API не используются.

**Документация FastAPI (Swagger/OpenAPI):** после запуска сервиса открой `http://localhost:8080/docs` в браузере (интерактивное тестирование эндпоинтов) или `http://localhost:8080/openapi.json` (машиночитаемое описание API). Это одинаково работает и для ручного запуска `uvicorn`, и для запуска через `docker-compose`/`docker compose`, если API опубликован на `localhost:8080`.

**Стек:** FastAPI (Python 3.11), Server-Sent Events, Docker, **`luac`**, **Rich** + **prompt_toolkit** (CLI), Next.js (Web UI).

**Диаграммы C1–C3 (Mermaid):** [docs/архитектура_С4_визуал.md](docs/архитектура_С4_визуал.md) · **C4 (описание):** [docs/архитектура_С4-описание.md](docs/архитектура_С4-описание.md)

---

<a id="readme-2"></a>
## 2. **Быстрый запуск**

**Выберите профиль железа и выполните одну команду из корня репозитория.**

**Для стендов жюри с аппаратным ускорением (NVIDIA GPU)** — после установки [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html):

```bash
docker-compose -f docker-compose-nvidia-gpu.yml up --build -d
```

**Для обычных систем (CPU fallback)** — без GPU passthrough в compose:

```bash
docker-compose up --build -d
```

После старта: API — `http://localhost:8080`, Ollama — `http://localhost:11434`. Первый запуск может занять время (сборка образа, загрузка весов модели).

---

<a id="readme-3"></a>
## 3. Структура проекта

| Путь | Назначение |
|------|------------|
| `api/` | FastAPI: маршруты, оркестрация задач, **Guard**, **Agent**, **LuaValidator**, SSE |
| `cli-client/` | Интерактивный терминальный клиент (**Rich**, история ввода) |
| `web-ui/` | Веб-интерфейс (Next.js), чат, подключение к API и SSE |
| `prompts/` | Системные промпты генератора и guard |
| `docs/` | Контракты API, контекста, отладка, архитектура C4 |
| `tests/` | Автотесты и сценарии проверки |
| `docker-compose.yml` / `docker-compose-nvidia-gpu.yml` | Обычный и GPU-вариант стека |

---

<a id="readme-4"></a>
## 4. Клиенты

### CLI (интерактивный терминал)

Из корня репозитория (Python 3.11+, venv по желанию):

```bash
pip install -r requirements.txt
python cli-client/chat.py
```

Клиент на **Rich** и **prompt_toolkit**: история запросов **стрелками вверх/вниз**, ответы модели и код — с **подсветкой** (Markdown-блоки `lua` в панелях Rich). Базовый URL API по умолчанию: `http://localhost:8080`.

### Web UI

```bash
cd web-ui
npm install
npm run dev
```

Откройте `http://localhost:3000`. При необходимости задайте `NEXT_PUBLIC_API_BASE` (например `http://localhost:8080`).

---

<a id="readme-5"></a>
## 5. API (асинхронная модель)

Запрос **не блокирует** поток до готового кода: сервер принимает задачу и возвращает идентификатор; клиент подписывается на поток статусов.

| Метод | Описание |
|--------|----------|
| `POST /generate` | Тело: `{"prompt": "...", "context": "..."?}`. Ответ: `{"task_id": "<uuid>"}`. Задача ставится в очередь, пайплайн выполняется в фоне. |
| `GET /status?task_id=<uuid>` | **SSE** (`text/event-stream`). В теле событий — JSON с полями вроде `stage`, `message`, `code`, `error`. Типичные стадии: `pending`, `generating`, `validating`, `retrying`, `done`, `error`. |
| `GET /health` | Проверка готовности API и связи с Ollama/моделью. |

Подробные примеры и поля — в [docs/api_contract_description.md](docs/api_contract_description.md).

---

<a id="readme-6"></a>
## 6. Архитектурные контракты

- **Введение в проект с нуля:** [docs/ONBOARDING.md](docs/ONBOARDING.md).
- **Формат поля `context` для мульти-туровых диалогов** (защита от poisoning и инъекций через историю): [docs/КЛИЕНТ_КОНТЕКСТ_КОНТРАКТ.md](docs/КЛИЕНТ_КОНТЕКСТ_КОНТРАКТ.md).
- **HTTP-контракт и SSE:** [docs/api_contract_description.md](docs/api_contract_description.md).
- **Security Guard:** отдельный проход по промпту/контексту (Ollama `/api/chat` + правила в `api/guard.py` и промпте guard); при срабатывании блокировки клиент получает завершение с маркером безопасности в коде.
- **LuaValidator:** вызов системного **`luac`** к сгенерированному коду; при ошибке синтаксиса текст ошибки подмешивается в следующую попытку генерации (**до 3 раз**, `MAX_RETRIES`). Локально без `luac` можно выставить `DRY_RUN=true` (см. [docs/DEBUGGING.md](docs/DEBUGGING.md)).

Диаграммы уровней C1–C3: [docs/архитектура_С4_визуал.md](docs/архитектура_С4_визуал.md). Уровень **C4 (описание)** — [docs/архитектура_С4-описание.md](docs/архитектура_С4-описание.md).

---

<a id="readme-7"></a>
## 7. Ручной запуск (Ollama + uvicorn, без Docker)

Сценарий для разработки: три и более терминалов из **корня репозитория**. Подробные команды, переменные окружения, таблица тестов и примеры для CLI/Web UI — в [docs/ONBOARDING.md §12](docs/ONBOARDING.md#12-ручной-локальный-запуск-ollama-модели-uvicorn-тесты-cli-web-ui); типичные сбои (прокси, PS 5.1, UTF-8) — в [docs/DEBUGGING.md §3](docs/DEBUGGING.md#3-сценарий-b-ручной-запуск-windows-без-docker).

1. **Ollama** — в первом терминале: `OLLAMA_KEEP_ALIVE=-1` (или в PowerShell `$env:OLLAMA_KEEP_ALIVE = "-1"`), затем **`ollama serve`**. Во втором терминале один раз: **`ollama pull qwen2.5-coder:7b-instruct-q4_K_M`** (или легче **`ollama pull qwen2.5-coder:0.5b`**). Имя модели должно совпасть с **`OLLAMA_MODEL`** у API. Для быстрой проверки весов без FastAPI можно **`ollama run`** с тем же именем модели, что после `pull` (интерактивный режим Ollama).
2. **API** — активировать venv, выставить **`NO_PROXY`**, **`DRY_RUN`**, **`OLLAMA_BASE_URL`**, **`OLLAMA_MODEL`**, **`MAX_RETRIES`**, при необходимости **`OLLAMA_NUM_CTX`** / **`OLLAMA_NUM_PREDICT`**, затем **`uvicorn api.main:app --reload --host 127.0.0.1 --port 8080`**.
3. **Проверка** — `curl http://127.0.0.1:8080/health` или **`python tests/test_sse.py`**.
4. **Клиент** — интерактивно: **`python cli-client/chat.py`**; веб: **`cd web-ui`**, **`npm install`**, **`npm run dev`**, браузер **`http://localhost:3000`** (при другом хосте API задать **`NEXT_PUBLIC_API_BASE`**).

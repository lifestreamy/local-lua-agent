# README_CURSOR_TEMORARY

## 1) Что это за проект

`LocalScript` — локальная система генерации Lua-кода для сценариев MWS Octapi.

Система состоит из:
- backend API на FastAPI (`api/`)
- локальной LLM через Ollama (`qwen2.5-coder:7b-instruct-q4_K_M`)
- web-интерфейса на Next.js (`web-ui/`)
- набора тестов и сценариев проверки (`tests/`)

Основной runtime-контур:
1. UI/клиент отправляет `POST /generate` с `prompt` и опциональным `context`.
2. API запускает задачу и возвращает `task_id`.
3. Клиент читает SSE поток `GET /status?task_id=...`.
4. На стороне API: guard -> генерация через Ollama -> валидация `luac` -> retry loop.

## 2) Структура репозитория

- `api/` — FastAPI-приложение, доменная логика пайплайна, guard, validator.
- `web-ui/` — Next.js 16 UI, чат, локальное хранение истории, интеграция с SSE.
- `prompts/` — системные промпты генератора и guard.
- `tests/` — e2e/контрактные тесты, инъекции, SSE и сессионные сценарии.
- `docs/` — контракт API, архитектурные заметки, служебная документация.
- `docker-compose.yml`, `Dockerfile` — запуск полного стека в контейнерах.
- `requirements.txt` — зависимости Python API.

## 3) Как запускать (рекомендуемо: Docker)

### Требования
- Docker + Docker Compose
- GPU (рекомендуется, особенно для стабильной скорости генерации)

### Шаги
1. Из корня проекта:
   - `docker-compose up --build`
2. Проверка API:
   - `GET http://localhost:8080/health`
3. Проверка генерации:
   - `POST http://localhost:8080/generate` с JSON `{"prompt":"..."}`.
4. UI (локально через Node) запускается отдельно, см. раздел 5.

`docker-compose.yml` поднимает сервисы:
- `ollama` (порт `11434`)
- `model-puller` (одноразово тянет модель)
- `api` (порт `8080`)

## 4) Как запускать backend локально (без Docker)

### Требования
- Python 3.11+
- установленный Ollama

### Шаги
1. Установить зависимости:
   - `pip install -r requirements.txt`
2. Запустить Ollama:
   - `ollama serve`
3. Запустить API:
   - `uvicorn api.main:app --reload --port 8080`

Полезные переменные окружения:
- `OLLAMA_BASE_URL` (по умолчанию `http://ollama:11434`)
- `OLLAMA_MODEL` (по умолчанию `qwen2.5-coder:7b-instruct-q4_K_M`)
- `MAX_RETRIES` (по умолчанию `3`)
- `DRY_RUN` (`true` отключает `luac`-валидацию; удобно на Windows без Lua)

## 5) Как запускать web-ui

Из папки `web-ui/`:
1. `npm install`
2. `npm run dev`
3. Открыть `http://localhost:3000`

Опционально:
- `NEXT_PUBLIC_API_BASE` для явного указания адреса API (иначе используется `http://localhost:8080` в клиентской библиотеке UI).

Что делает UI:
- хранит чаты/черновики в `localStorage`
- отправляет `prompt/context` в API
- получает статусы и код по SSE
- отображает стадии (`pending`, `generating`, `validating`, `retrying`, `done`, `error`)

## 6) Ключевые backend-модули

- `api/main.py`
  - endpoint'ы: `/health`, `/generate`, `/status`
  - in-memory реестр задач `TASKS`
  - SSE выдача статусов по task id
- `api/agent.py`
  - `AgentPipeline.generate_stream(...)`
  - генерация через Ollama (`/api/generate`)
  - парсинг `<code>...</code>`/fenced code
  - retry-loop с `MAX_RETRIES`
- `api/guard.py`
  - pre-check prompt'а на безопасность и оффтоп
  - fallback на `SECURITY_BLOCK`
- `api/validator.py`
  - синтаксическая проверка Lua через `luac`
- `api/prompt_builder.py`
  - сборка финального промпта из system prompt + context + error context

## 7) API контракт (актуально для UI)

- `POST /generate`
  - вход: `{"prompt": "...", "context": "..."?}`
  - выход: `{"task_id":"..."}`
- `GET /status?task_id=...` (SSE)
  - поток `data: {"stage","message","code","error"}`
- `GET /health`
  - проверка доступности API/Ollama/модели

Подробности: `docs/api_contract_description.md`.

## 8) Тестирование

Основные сценарии в `tests/`:
- `test_sse.py` — базовая проверка async + SSE потока
- `test_prompt_injection.py` — проверка guard (safe/unsafe prompts)
- `test_base_cases.py` — набор базовых проверок качества генерации
- `test_session_contract.py` — многотуровые сценарии с контекстом

Запуск примера:
- `python -m unittest tests.test_prompt_injection`
- `python -m unittest tests.test_base_cases`

## 9) Практические замечания

- На Windows для локальной разработки часто используют `DRY_RUN=true`, если нет `luac`.
- Для полной валидации синтаксиса Lua лучше запуск через Docker (там `luac` установлен).
- SSE-контракт важен для UI: при изменении полей статуса нужно синхронно обновлять `web-ui/lib/api.js`.

## 10) Где смотреть дальше

- Общая документация: `README.md`, `ONBOARDING.md`, `DEBUGGING.md`
- Архитектура: `docs/architecture/` и `docs/architecture_temorary_c4.md`

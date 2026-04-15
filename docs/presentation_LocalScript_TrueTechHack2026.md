# Презентация LocalScript — True Tech Hack 2026

---

## LocalScript

- True Tech Hack 2026 · трек 2
- Локальный ИИ-ассистент для генерации и проверки Lua под MWS Octapi LowCode
- Qwen2.5-Coder 7B · Ollama · FastAPI · SSE · luac

---

## Проблема

- Бизнес-аналитики описывают логику процессов словами, а в Octapi нужен исполняемый Lua.
- Одна и та же задача формулируется по-разному — шаблоны и поиск по строкам не масштабируются.
- Нужна изоляция от облачных LLM и предсказуемая среда для стенда жюри.

---

## Решение

- Контур полностью локальный: Docker + Ollama + собственный API.
- Асинхронная модель: POST /generate → task_id, затем SSE /status со стадиями пайплайна.
- Цикл качества: парсинг ответа → luac → до 3 попыток исправления синтаксиса.

---

## Продуктовая ценность

- Сокращение времени от формулировки до рабочего скрипта в шаге процесса.
- Поддержка мульти-турового контекста (CLI и Web UI) по [КЛИЕНТ_КОНТЕКСТ_КОНТРАКТ.md](КЛИЕНТ_КОНТЕКСТ_КОНТРАКТ.md).
- Прозрачность для пользователя: видны стадии генерации, валидации и повторов.

---

## Для кого

- Аналитики и внедренцы MWS Octapi — быстрый черновик Lua из текста задачи.
- Команды с требованием private / air-gapped — без внешних API к LLM.
- Жюри хакатона — воспроизводимый docker-compose (GPU и CPU-профили).

---

## Архитектура — контекст (C1)

- Пользователь → CLI или Web UI → система LocalScript → готовый Lua в Octapi.
- См. визуал: `docs/архитектура_С4_визуал.md` (Mermaid flowchart).

---

## Архитектура — контейнеры (C2)

- Клиенты обращаются к FastAPI :8080 (JSON + SSE).
- Backend: httpx к Ollama :11434; subprocess luac для синтаксиса.
- Описание C4: `docs/архитектура_С4-описание.md`.

---

## Архитектура — компоненты (C3)

- `api/main.py` — маршруты, TASKS, фоновые задачи, EventSourceResponse.
- `api/guard.py` — изолированная проверка промпта (Ollama /api/chat).
- `api/agent.py` — AgentPipeline, retry; `api/validator.py` — luac; `api/prompt_builder.py`.

---

## Безопасность и качество кода

- Security Guard: хард-блок фразы + классификация SAFE/UNSAFE, sanitize вывода.
- LuaValidator: `luac -o /dev/null -`; при `DRY_RUN=true` проверка отключена (только dev).
- Лимиты длины context на сервере для защиты от OOM и переполнения контекста модели.

---

## API (кратко)

- `POST /generate` — `{ prompt, context? }` → `{ task_id }`.
- `GET /status?task_id=…` — SSE: stage, message, code, error.
- `GET /health` — связность API, Ollama и наличие модели. Подробности: `docs/api_contract_description.md`.

---

## Клиенты

- CLI: `python cli-client/chat.py` — Rich, история стрелками, подсветка кода.
- Web UI: `cd web-ui && npm run dev` — `NEXT_PUBLIC_API_BASE` при необходимости.

---

## Запуск для стенда

- NVIDIA GPU: `docker-compose -f docker-compose-nvidia-gpu.yml up --build -d`
- CPU fallback: `docker-compose up --build -d`
- Полная инструкция: `README.md` в корне репозитория.

---

## Итог

- LocalScript связывает естественный язык, локальную LLM и жёсткую проверку Lua.
- Готовность к демо: compose, CLI и Web UI, контракт контекста и SSE.
- Репозиторий команды: task-repo (GitLab TrueTechHack2026).

---



- Соответствие треку: локальность, Octapi/Lua, отсутствие облачных LLM в рантайме.
- Инженерия: ясная архитектура, контракты API и контекста, тесты и Docker.
- Ценность: экономия времени аналитика, предсказуемый UX стадий генерации.
- Демо: один сценарий «запрос → SSE → код в Octapi» воспроизводим с README.


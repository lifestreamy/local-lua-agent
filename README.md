# LocalScript — Локальный генератор Lua-кода для MWS Octapi

Агентная система для **True Tech Hack 2026, Трек 2**.

Принимает задачу на естественном языке (русском или английском) и генерирует валидный Lua-код
для платформы **MWS Octapi LowCode**. Работает полностью локально — никаких облачных API,
никакого интернет-соединения не требуется.

---

## Что делает система и зачем нужен LLM

MWS Octapi — это платформа автоматизации бизнес-процессов (workflow engine).
Бизнес-аналитик создаёт сценарии («процессы»): шаги, условия, ветки.
Каждый шаг может содержать фрагмент Lua-кода, который что-то делает с данными рабочего процесса.
Все переменные хранятся в `wf.vars.*`, к которым Lua-скрипт имеет доступ.

**Задача системы** — позволить аналитику описать нужную операцию на обычном русском языке,
а получить в ответ готовый рабочий Lua-код, который можно вставить в платформу.

### Почему нельзя использовать шаблоны или поиск по таблице?

Рассмотрим пример. Бизнес-аналитик пишет:

> *«Оставить в списке только клиентов, у которых поле `isVerified` равно `true`
> и сумма покупок больше 5000»*

Другой аналитик хочет то же самое, но формулирует иначе:

> *«Из массива `wf.vars.clients` выбрать тех, кто верифицирован и потратил более пяти тысяч»*

Слова разные — смысл одинаковый — правильный Lua-код одинаковый:

```lua
local result = _utils.array.new()
for _, c in ipairs(wf.vars.clients) do
  if c.isVerified and c.totalSpend > 5000 then
    table.insert(result, c)
  end
end
return result
```

Шаблонный движок не справится: он ищет точное совпадение строк.
LLM понимает **семантику** запроса — намерение, смысл, контекст — независимо от формулировки.
Именно для этого здесь нужна языковая модель.

### Область применения

Система предназначена **только** для задач автоматизации MWS Octapi:
операции над массивами `wf.vars.*`, строковые операции, арифметика, условия, фильтрация.
Она не является универсальным Lua-ассистентом. Запрос «напиши алгоритм Фибоначчи» не входит
в область применения — платформа MWS для этого не используется.

---

## Архитектура системы

### C1 — Контекст: что система делает

```
Пользователь / платформа MWS Octapi
        │
        │  POST /generate
        │  {"prompt": "оставить только верифицированных клиентов"}
        ▼
┌─────────────────────┐
│   LocalScript API   │
│  (этот репозиторий) │
└─────────────────────┘
        │
        │  {"code": "local result = _utils.array.new() ..."}
        ▼
Готовый Lua-код вставляется в шаг платформы MWS Octapi
```

---

### C2 — Контейнеры: из чего состоит система

```
Компьютер пользователя
══════════════════════════════════════════════════════════════════
  ┌──────────────────────────────┐   ┌──────────────────────────────────┐
  │  ПРОЦЕСС 1: Ollama           │   │  ПРОЦЕСС 2: uvicorn              │
  │  Движок локальных LLM        │   │  Python HTTP API-сервер          │
  │                              │   │                                  │
  │  Порт: 11434                 │   │  Порт: 8080                      │
  │  Хранит веса модели на диске │   │  Содержит бизнес-логику          │
  │  Загружает модель в GPU VRAM │   │  Кода AI внутри нет              │
  │  при первом запросе          │   │                                  │
  │                              │◄──│  httpx POST /api/generate        │
  │  POST /api/generate          │   │  (делегирует генерацию в Ollama) │
  │    → запускает LLM на GPU    │   │                                  │
  └──────────────────────────────┘   └──────────────────────────────────┘
                                                ▲
                                                │ POST /generate {"prompt":"..."}
                                           [ Вы / тест ]
                                           curl, PowerShell, MWS

При Docker Compose оба процесса — отдельные контейнеры, общаются через
внутреннюю сеть Docker (service name: ollama:11434, не localhost).
```

**Аналогия:** uvicorn — это официант (принимает заказ, несёт ответ).
Ollama — кухня (делает реальную работу). Если кухня не работает — официант
ответит, но тарелка будет пустой.

---

### C3 — Компоненты внутри API (Python)

```
POST /generate {"prompt": "..."}
        │
        ▼
api/main.py  ──  FastAPI endpoint
        │        Запускает warm-up модели при старте сервера
        ▼
api/agent.py  ──  AgentPipeline
        │
        ├─ 1. api/prompt_builder.py
        │      Читает prompts/system_prompt.txt
        │      Добавляет 20 few-shot примеров Lua для MWS
        │      Добавляет запрос пользователя
        │      → готовый промпт (~1600 токенов)
        │
        ├─ 2. OllamaClient (api/agent.py)
        │      httpx POST → ollama:11434/api/generate
        │      Модель: qwen2.5-coder:7b-instruct-q4_K_M
        │      Параметры: num_ctx=4096, temperature=0.1
        │      → сырой текст ответа модели
        │
        ├─ 3. Парсер CoT (api/agent.py)
        │      Извлекает содержимое тега <code>...</code>
        │      → чистый Lua-код
        │
        ├─ 4. api/validator.py
        │      Запускает: echo <code> | luac -o /dev/null -
        │      DRY_RUN=true → пропустить (Windows без luac)
        │      → (valid: True) или (valid: False, error: "...")
        │
        └─ 5. Если невалидно и попытки остались:
               Добавить ошибку luac в промпт → повторить (макс. 3×)
               Если все попытки исчерпаны → вернуть лучший вариант

        ▼
{"code": "<raw Lua string>"}
```

---

### Зачем Chain-of-Thought (CoT)?

Системный промпт требует от модели сначала написать рассуждение, затем код:

```
<thinking>
1. Перевод задачи на английский
2. Пошаговый план Lua-логики с учётом MWS API
</thinking>
<code>
[только сырой Lua]
</code>
```

Записывая рассуждение **перед** кодом, модель использует эти токены как контекст
для собственной генерации — буквально «думает вслух» перед тем как писать.
Это значительно повышает точность для нестандартных запросов.

API возвращает только содержимое тега `<code>` — рассуждение остаётся внутри.

---

## Структура файлов репозитория

```
task-repo/
│
├── README.md                   ← этот файл
│
├── ONBOARDING.md               ← введение в проект для команды
│
├── Dockerfile                  ← образ Python API: python:3.11-slim + lua5.4
│
├── docker-compose.yml          ← два сервиса: api (8080) + ollama (11434)
│
├── requirements.txt            ← зависимости: fastapi, uvicorn, pydantic, httpx
│
├── api/
│   ├── __init__.py
│   ├── main.py                 ← FastAPI app, /generate + /health, lifespan warm-up
│   ├── models.py               ← Pydantic: GenerateRequest, GenerateResponse
│   ├── agent.py                ← AgentPipeline, OllamaClient, CoT-парсер, retry loop
│   ├── validator.py            ← LuaValidator: luac subprocess, DRY_RUN bypass
│   └── prompt_builder.py       ← сборка промпта: system_prompt + error context
│
├── prompts/
│   └── system_prompt.txt       ← CoT-шаблон + 20 few-shot примеров MWS Lua на русском
│                                 (главный файл для улучшения качества генерации)
│
└── tests/
    ├── test_base_cases_data.py ← словарь тест-кейсов (эталонный Lua + перефразировки)
    ├── test_base_cases.py      ← unittest-раннер, тестирует API, собирает метрики
    └── reports/                ← папка для Markdown/JSON отчетов по результатам тестов (в .gitignore)
```

---

## Требования

- Docker + Docker Compose (для продакшн-запуска)
- GPU с ≥ 8 ГБ VRAM
  - AMD RX 7000+: поддержка ROCm (проверено на RX 7800 XT)
  - NVIDIA: NVIDIA Container Toolkit для GPU passthrough в Docker
- Для локальной разработки без Docker: Python 3.11+, Ollama

---

## Быстрый старт (Docker Compose)

> ⚠️ **Docker Compose не подвержен проблемам с системным прокси** (Clash Verge и др.).
> Контейнеры общаются через изолированную внутреннюю сеть Docker. Прокси Windows
> не затрагивает трафик между контейнерами.

### 1. Скачать модель (один раз)

```bash
docker-compose run --rm ollama ollama pull qwen2.5-coder:7b-instruct-q4_K_M
```

### 2. Запустить

```bash
docker-compose up --build
```

### 3. Проверить

```bash
curl -X POST http://localhost:8080/generate \
     -H "Content-Type: application/json" \
     -d '{"prompt": "получить последний email из списка"}'
```

Ожидаемый ответ:
```json
{"code": "return wf.vars.emails[#wf.vars.emails]"}
```

---

## Тестирование

Для проверки качества модели и устойчивости промптов используется тестовый набор:
```bash
python -m unittest tests.test_base_cases.TestBaseCases
```
Тест-раннер отправит десятки перефразированных запросов к локальному API, сравнит ответы с эталонным Lua-кодом и сохранит детальные отчеты (в формате `.md` и `.json`) в папку `tests/reports/`.

---

## Локальная разработка (без Docker, Windows)

```powershell
# 1. Активировать venv
.venv\Scripts\activate

# 2. Установить зависимости
pip install -r requirements.txt
```

### ⚠️ Системный прокси (Clash Verge, Proxifier и др.)

Если включён системный прокси — Python направит ВСЕ HTTP-запросы через него,
включая запросы к `localhost:11434`. Прокси не умеет маршрутизировать локальный
трафик и вернёт `502 Bad Gateway`. PowerShell при этом работает нормально —
у него другой сетевой стек (.NET HttpClient), который обходит прокси для loopback.

**Решение:** добавить исключение для localhost (один раз):
```powershell
$env:NO_PROXY = "localhost,127.0.0.1,::1"
```
Или через «Переменные среды» → «Системные переменные» → добавить `NO_PROXY`.

---

```powershell
# 3. Запустить Ollama через CLI (не через GUI):
$env:OLLAMA_KEEP_ALIVE = "-1"   # модель не выгружается из VRAM автоматически
ollama serve
# Оставить этот терминал открытым

# 4. В отдельном терминале — проверить, что Ollama отвечает:
Invoke-RestMethod -Uri http://localhost:11434/api/generate -Method POST \
  -ContentType "application/json" \
  -Body '{"model":"qwen2.5-coder:7b-instruct-q4_K_M","prompt":"hello","stream":false}'

# 5. В отдельном терминале — запустить uvicorn:
$env:NO_PROXY = "localhost,127.0.0.1,::1"
$env:DRY_RUN = "true"
$env:OLLAMA_BASE_URL = "http://localhost:11434"
$env:OLLAMA_MODEL = "qwen2.5-coder:7b-instruct-q4_K_M"
uvicorn api.main:app --reload --port 8080
# При первом старте: warm-up займёт ~10-15с (модель загружается в VRAM)
```

# DEBUGGING.md — Руководство по отладке LocalScript

> Расположение в репозитории: `docs/DEBUGGING.md`

Этот документ описывает все реальные баги, с которыми мы столкнулись в ходе разработки,
как они были диагностированы и решены, а также рабочие процессы для итерационной
отладки модели и промптов.

---

## Содержание

1. [Выбор сценария запуска](#1-выбор-сценария-запуска)
2. [Сценарий A: Docker Compose (продакшн)](#2-сценарий-a-docker-compose-продакшн)
3. [Сценарий B: Ручной запуск (Windows, без Docker)](#3-сценарий-b-ручной-запуск-windows-без-docker)
4. [Рабочие процессы отладки промптов](#4-рабочие-процессы-отладки-промптов)
5. [Известные баги и их решения](#5-известные-баги-и-их-решения)
6. [Быстрая диагностическая шпаргалка](#6-быстрая-диагностическая-шпаргалка)

---

## 1. Выбор сценария запуска

Прежде чем начать — определись, что тебе нужно:

```
Хочу...                                            → Используй
────────────────────────────────────────────────────────────────
Запустить всё и проверить что работает              → Сценарий A (Docker Compose)
Быстро менять код Python и перезапускать            → Сценарий B (uvicorn --reload)
Итерировать по system_prompt.txt без API            → Workflow 1 (Raw Ollama)
Отлаживать сборку промпта в Python                  → Workflow 2 (Python-скрипт)
Проверить полный пайплайн (async)                    → Workflow 3 (`POST /generate` + SSE `/status` или `python tests/test_sse.py`)
Измерить точность на всём тест-сете                 → Workflow 4 (unittest runner)
```

---

## 2. Сценарий A: Docker Compose (продакшн)

Все компоненты поднимаются одной командой. Рекомендуется для финального тестирования
и демонстрации. Не подходит для быстрой итерации по коду.

### 2.1 Первый запуск (скачать модель)

```bash
# Скачать модель в volume ollama-data (только один раз, ~4.7 ГБ):
docker-compose run --rm ollama ollama pull qwen2.5-coder:7b-instruct-q4_K_M
```

После этого модель хранится в Docker volume и не скачивается повторно.

### 2.2 Запуск

```bash
docker-compose up --build
```

При первом старте: сборка образа `api` (~1-2 мин) + warm-up модели (~10-15 с).

### 2.3 Проверка — curl (Linux / macOS / Git Bash)

API **асинхронный**: `POST /generate` возвращает только `{"task_id":"..."}`; готовый Lua приходит в потоке **SSE** на `GET /status?task_id=...` (события с JSON, у завершения обычно `stage":"done"` и поле `code`).

```bash
# 1) Отправить задачу:
curl -sS -X POST http://localhost:8080/generate \
     -H "Content-Type: application/json" \
     -d '{"prompt": "получить последний email из списка"}'
# Ожидаемый ответ: {"task_id":"<uuid>"}

# 2) Подставь task_id из шага 1 и слушай SSE до done/error:
curl -sN "http://localhost:8080/status?task_id=<uuid>"

# Health (проверка API и связи с Ollama/моделью):
curl -sS http://localhost:8080/health
```

Проще всего прогнать весь цикл одной командой: **`python tests/test_sse.py`** (сервер должен быть запущен).

### 2.4 Проверка — PowerShell 7+ (pwsh)

`POST /generate` через `Invoke-RestMethod` удобен; для **SSE** на Windows надёжнее **curl** из Git Bash / WSL или скрипт `python tests/test_sse.py`.

```powershell
Invoke-RestMethod -Uri http://localhost:8080/generate `
    -Method POST `
    -ContentType "application/json; charset=utf-8" `
    -Body '{"prompt": "получить последний email из списка"}'
# Ожидается объект с полем task_id
```

### 2.5 Проверка — PowerShell 5.1 (встроенный в Windows)

```powershell
# ОБЯЗАТЕЛЬНО передавать тело как UTF-8 байты (см. Баг #1 ниже):
$json  = '{"prompt": "получить последний email из списка"}'
$bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
Invoke-RestMethod -Uri http://localhost:8080/generate `
    -Method POST `
    -ContentType "application/json; charset=utf-8" `
    -Body $bytes
# Ответ: task_id; для полного пайплайна — curl SSE или python tests/test_sse.py
```

### 2.6 Остановка

```bash
docker-compose down          # остановить, сохранить volume с моделью
docker-compose down -v       # остановить и удалить volume (потребует повторного скачивания)
```

---

## 3. Сценарий B: Ручной запуск (Windows, без Docker)

Используется при активной разработке: изменения в Python-коде видны сразу без пересборки образа.
Требует: Python 3.11+, pip, установленный Ollama CLI.

### 3.1 Терминал 1 — Запуск Ollama

```powershell
# Не выгружать модель из VRAM при простое (иначе каждый запрос будет ждать загрузки):
$env:OLLAMA_KEEP_ALIVE = "-1"
ollama serve
# Оставить этот терминал открытым!
```

> **Важно:** Запускай Ollama через CLI (`ollama serve`), а не через GUI-приложение.
> GUI не позволяет задать переменные среды.

### 3.2 Скачать модель и проверить Ollama (любой другой терминал)

Один раз на машину (пока работает `ollama serve`):

```powershell
ollama pull qwen2.5-coder:7b-instruct-q4_K_M
# или легче для CPU:
ollama pull qwen2.5-coder:0.5b
```

Для «живого» диалога с моделью без FastAPI: **`ollama run qwen2.5-coder:0.5b`** (или другое скачанное имя).

Проверка, что Ollama отвечает (подставь имя модели, совпадающее с будущим `OLLAMA_MODEL`):

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:11434/api/generate -Method POST `
    -ContentType "application/json" `
    -Body '{"model":"qwen2.5-coder:7b-instruct-q4_K_M","prompt":"hello","stream":false}'
# Ожидаемый ответ: объект с полем response
```

### 3.3 Терминал 2 — Запуск uvicorn

```powershell
# Активировать виртуальное окружение:
.venv\Scripts\activate

# Настроить переменные среды:
$env:NO_PROXY           = "localhost,127.0.0.1,::1"  # обойти системный прокси
$env:DRY_RUN            = "true"                      # пропустить luac (нет на Windows)
$env:OLLAMA_BASE_URL    = "http://127.0.0.1:11434"
$env:OLLAMA_MODEL       = "qwen2.5-coder:7b-instruct-q4_K_M"   # или qwen2.5-coder:0.5b
$env:MAX_RETRIES        = "3"
$env:OLLAMA_NUM_CTX     = "3072"
$env:OLLAMA_NUM_PREDICT = "1024"

# Запустить сервер с hot-reload:
uvicorn api.main:app --reload --host 127.0.0.1 --port 8080

# Ждать строки: Application startup complete.
# Первый запрос к модели после старта Ollama может занять время, пока веса подгрузятся в память.
```

### 3.4 Терминал 3 — Тестовые запросы к API (async)

`POST /generate` возвращает **`task_id`**. Готовый Lua — в **SSE** `GET /status?task_id=...`. Полный сценарий с командами для Ollama, uvicorn, тестов, CLI и Web UI — в [ONBOARDING.md §12](ONBOARDING.md#12-ручной-локальный-запуск-ollama-модели-uvicorn-тесты-cli-web-ui).

**Через curl (Git Bash / WSL):**

```bash
curl -sS -X POST http://127.0.0.1:8080/generate \
     -H "Content-Type: application/json" \
     -d '{"prompt": "отфильтровать заказы со статусом выполнен"}'
# {"task_id":"..."}

curl -sN "http://127.0.0.1:8080/status?task_id=<uuid_из_ответа>"
```

**Через PowerShell 5.1 (UTF-8 тело) — только шаг submit:**

```powershell
$json  = '{"prompt": "отфильтровать заказы со статусом выполнен"}'
$bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
Invoke-RestMethod -Uri http://127.0.0.1:8080/generate `
    -Method POST -ContentType "application/json; charset=utf-8" -Body $bytes
```

**Через PowerShell 5.1 — с файлом (альтернатива):**

```powershell
'{"prompt": "отфильтровать заказы со статусом выполнен"}' | `
    Out-File -Encoding utf8NoBOM body.json

Invoke-RestMethod -Uri http://127.0.0.1:8080/generate `
    -Method POST -ContentType "application/json; charset=utf-8" -InFile body.json
```

**Цикл целиком (рекомендуется):**

```powershell
python tests/test_sse.py
```

### 3.5 Тесты, CLI и Web UI (ручная проверка)

**Тесты** (из корня, API для сетевых сценариев должен слушать `:8080`):

```powershell
python tests/test_sse.py
python -m unittest tests.test_prompt_injection -v
python tests/test_session_contract.py
python tests/test_session_stress.py
python -m unittest tests.test_request -v
```

`tests/test_base_cases.py` ожидает в ответе `POST /generate` поле **`code`** (старый контракт); при текущем API с **`task_id`** + SSE этот прогон **не совпадает** с ответом сервера, пока тест не переписан. См. таблицу в ONBOARDING §12.

**CLI-клиент:**

```powershell
pip install -r requirements.txt
python cli-client/chat.py
```

Внутри сессии: обычный текст — запрос; **`exit`** — выход; **`clear`** — сброс накопленного `context`; стрелки — история ввода.

**Web UI:**

```powershell
cd web-ui
npm install
npm run dev
```

Браузер: `http://localhost:3000`. Если API не на `localhost:8080`, перед `npm run dev`: `$env:NEXT_PUBLIC_API_BASE = "http://127.0.0.1:8080"`.

---

## 4. Рабочие процессы отладки промптов

### Workflow 1 — Raw Ollama (обход всего Python-кода)

**Когда использовать:** хочешь проверить, как модель реагирует на промпт,
не меняя Python-код. Самая быстрая петля итерации.

```powershell
# Сформировать промпт вручную и отправить напрямую в Ollama:
$prompt = @"
You are a Lua code generator for MWS Octapi platform.

<thinking>
1. Translate task to English
2. Plan the Lua logic step by step
</thinking>
<code>
[pure Lua here]
</code>

USER TASK: filter orders where status equals done
"@

$body = @{
    model  = "qwen2.5-coder:7b-instruct-q4_K_M"
    prompt = $prompt
    stream = $false
} | ConvertTo-Json -Depth 5

$bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
$r = Invoke-RestMethod -Uri http://localhost:11434/api/generate `
    -Method POST -ContentType "application/json; charset=utf-8" -Body $bytes
Write-Host $r.response
```

Или через Python — удобнее для длинных промптов:

```python
import httpx

system_prompt = open("prompts/system_prompt.txt", encoding="utf-8").read()
user_task = "отфильтровать заказы со статусом выполнен"
full_prompt = f"{system_prompt}\n\nUSER TASK: {user_task}"

r = httpx.post("http://localhost:11434/api/generate", json={
    "model": "qwen2.5-coder:7b-instruct-q4_K_M",
    "prompt": full_prompt,
    "stream": False
}, timeout=60)
print(r.json()["response"])
```

---

### Workflow 2 — Python-скрипт (тест PromptBuilder + Ollama)

**Когда использовать:** хочешь проверить, как PromptBuilder собирает финальный промпт,
без запуска uvicorn. Позволяет видеть и изменять сборку промпта в Python-коде.

```python
# debug_prompt.py — запустить из корня репозитория
import sys, os
sys.path.insert(0, ".")
os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"
os.environ["OLLAMA_MODEL"]    = "qwen2.5-coder:7b-instruct-q4_K_M"
os.environ["DRY_RUN"]         = "true"

from api.prompt_builder import PromptBuilder
from api.agent import OllamaClient

builder = PromptBuilder()
client  = OllamaClient()

user_prompt = "отфильтровать заказы со статусом выполнен"

# Посмотреть финальный промпт перед отправкой:
full_prompt = builder.build(user_prompt)
print("=== ФИНАЛЬНЫЙ ПРОМПТ ===")
print(full_prompt[:2000])  # первые 2000 символов

# Отправить и получить ответ:
print("\n=== ОТВЕТ МОДЕЛИ (RAW) ===")
raw = client.generate(full_prompt)
print(raw)
```

Запустить:
```powershell
$env:NO_PROXY = "localhost,127.0.0.1,::1"
python debug_prompt.py
```

---

### Workflow 3 — Полный пайплайн через API (async)

**Когда использовать:** uvicorn запущен, нужно прогнать запрос через весь стек:
Guard → PromptBuilder → OllamaClient → CoT-парсер → LuaValidator, с прогрессом по SSE.

Самый короткий путь: **`python tests/test_sse.py`**.

Пример на **httpx** (одна задача: submit + чтение SSE до `done`/`error`):

```python
import json
import httpx

API = "http://127.0.0.1:8080"
prompt = "отфильтровать заказы со статусом выполнен"

with httpx.Client(timeout=120.0) as client:
    r = client.post(f"{API}/generate", json={"prompt": prompt})
    r.raise_for_status()
    task_id = r.json()["task_id"]

    with client.stream("GET", f"{API}/status", params={"task_id": task_id}) as stream:
        stream.raise_for_status()
        for line in stream.iter_lines():
            if not line or not line.startswith("data: "):
                continue
            payload = json.loads(line.removeprefix("data: "))
            print(payload.get("stage"), payload.get("message"))
            if payload.get("stage") in ("done", "error"):
                print("code:", payload.get("code"))
                print("error:", payload.get("error"))
                break
```

```bash
# curl: только submit; для SSE подставь task_id вручную:
curl -sS -X POST http://127.0.0.1:8080/generate \
     -H "Content-Type: application/json" \
     -d '{"prompt": "отфильтровать заказы со статусом выполнен"}' | python -m json.tool
```

---

### Workflow 4 — Полный тест-сет (измерение точности)

**Когда использовать:** после изменения `system_prompt.txt` — для количественной
оценки влияния изменений на точность.

**Важно:** `tests/test_base_cases.py` по-прежнему читает поле **`code`** из ответа **`POST /generate`**. Текущий API возвращает **`task_id`** и отдаёт код через **SSE**. Пока тест не обновлён под async, этот workflow **не отражает** продакшн-контракт; для проверки живого API используй Workflow 3 или `python tests/test_sse.py`.

```bash
# Убедись что API запущен (Docker или uvicorn), затем:
python -m unittest tests.test_base_cases.TestBaseCases

# Отчёт сохраняется в tests/reports/report_YYYYMMDD_HHMMSS.{md,json}
```

Для просмотра последнего отчёта:
```powershell
Get-ChildItem tests/reports/ | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | Get-Content
```

---

## 5. Известные баги и их решения

---

### Баг #1 — PowerShell 5.1: кириллица становится `?????????`

**Симптом:**

```
PS> Invoke-RestMethod ... -Body '{"prompt":"Привет, ты понимаешь русский?"}'

response : I apologize, but I'm not able to understand or respond to the message you provided.
           It appears to be in a language I don't recognize.
```

Или, ещё хуже, модель «переводит» `???????` как что-то совершенно случайное:

```
response : The translation of "???????, ?? ????????? ?????????" is:
           "Look, how the stars are shining in the sky"
```

**Причина:**

PowerShell 5.1 (встроенный в Windows 10/11) кодирует строку в параметре `-Body`
как **ASCII**. Каждый символ вне ASCII-диапазона (U+0000–U+007F) заменяется на `?`.
Кириллица полностью в этом диапазоне не помещается — все символы теряются.

Это не баг модели. Qwen2.5-Coder обучена на 29+ языках и прекрасно понимает русский,
если получает его в правильной кодировке.

**Диагностика:**

Проверь версию PowerShell:
```powershell
$PSVersionTable.PSVersion
# Major 5 → проблема с кодировкой
# Major 7 → UTF-8 по умолчанию, проблем нет
```

**Решение 1 — UTF-8 байты (рекомендуется для PS 5.1):**

```powershell
$json  = '{"model":"qwen2.5-coder:7b-instruct-q4_K_M","prompt":"Привет, ты понимаешь русский?","stream":false}'
$bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
Invoke-RestMethod -Uri http://localhost:11434/api/generate `
    -Method POST -ContentType "application/json; charset=utf-8" -Body $bytes
```

**Решение 2 — файл с явной кодировкой utf8NoBOM:**

```powershell
'{"prompt": "отфильтровать заказы"}' | Out-File -Encoding utf8NoBOM body.json
Invoke-RestMethod -Uri http://localhost:8080/generate `
    -Method POST -ContentType "application/json; charset=utf-8" -InFile body.json
# Ответ содержит task_id; для кода Lua — SSE /status или python tests/test_sse.py
```

**Решение 3 — использовать PowerShell 7+:**

```powershell
# Установить: winget install Microsoft.PowerShell
# Запустить: pwsh (не powershell)
pwsh -Command 'Invoke-RestMethod -Uri http://localhost:8080/generate -Method POST -ContentType "application/json; charset=utf-8" -Body "{\"prompt\": \"отфильтровать заказы\"}"'
# Ответ: task_id; полный результат — через SSE /status или python tests/test_sse.py
```

**Решение 4 — curl (всегда работает, UTF-8 по умолчанию):**

```bash
curl -X POST http://localhost:8080/generate \
     -H "Content-Type: application/json" \
     -d '{"prompt": "отфильтровать заказы"}'
# Ответ: {"task_id":"..."}; дальше curl -sN "http://localhost:8080/status?task_id=..." или python tests/test_sse.py
```

**Влияние на продакшн:** нулевое. Python `httpx` всегда отправляет UTF-8.
Проблема касается только инструментов ручной отладки на Windows.

---

### Баг #2 — 502 Bad Gateway при запросах к localhost через Ollama / uvicorn

**Симптом:**

```
httpx.ProxyError: 502 Bad Gateway via proxy
```

или

```
[WinError 10061] Подключение не установлено
```

**Причина:**

Системный прокси-сервер (Clash Verge, Proxifier, корпоративный VPN-клиент и т.д.)
перехватывает ВСЕ HTTP-запросы Python, включая запросы к `localhost`.
Прокси не умеет маршрутизировать loopback-адреса и возвращает ошибку.

PowerShell при этом работает нормально — он использует .NET `HttpClient`,
который по умолчанию исключает `localhost` из прокси.

**Диагностика:**

```powershell
# Работает (PS не через прокси):
Invoke-RestMethod -Uri http://localhost:11434/api/generate ...

# Не работает (Python через прокси):
python -c "import httpx; print(httpx.get('http://localhost:11434').text)"
```

**Решение — добавить NO_PROXY перед запуском uvicorn:**

```powershell
$env:NO_PROXY = "localhost,127.0.0.1,::1"
uvicorn api.main:app --reload --port 8080
```

Или добавить в системные переменные среды раз и навсегда:
`Системные свойства → Переменные среды → Системные переменные → Создать`:
- Имя: `NO_PROXY`
- Значение: `localhost,127.0.0.1,::1`

**Влияние на Docker:** нулевое. Контейнеры общаются через внутреннюю Docker-сеть,
а не через системный прокси Windows.

---

### Баг #3 — `ModuleNotFoundError: No module named 'test_base_cases_data'`

**Симптом:**

```
ImportError: Failed to import test module: test_base_cases
...
ModuleNotFoundError: No module named 'test_base_cases_data'
```

**Причина:**

Файл был переименован из `test_base_case_data.py` в `test_base_cases_data.py`.
При запуске через PyCharm (gutter icon) или `python -m unittest tests.test_base_cases.TestBaseCases`
Python ищет модули относительно **корня проекта**, а не папки `tests/`.
Импорт `from test_base_cases_data import TEST_CASES` не находит модуль,
потому что ищет его в корне, а не в `tests/`.

**Решение — использовать абсолютный импорт:**

В файле `tests/test_base_cases.py` заменить:
```python
# Неправильно:
from test_base_cases_data import TEST_CASES

# Правильно:
from tests.test_base_cases_data import TEST_CASES
```

---

### Баг #4 — Модель выгружается из VRAM после 5 минут простоя

**Симптом:**

Первый запрос после паузы выполняется 15-20 секунд вместо обычных 1-3 секунд.
В логах Ollama: `model unloaded`.

**Причина:**

По умолчанию Ollama выгружает модель из VRAM через 5 минут без запросов
для освобождения памяти.

**Решение для локальной разработки:**

```powershell
$env:OLLAMA_KEEP_ALIVE = "-1"
ollama serve
```

Значение `-1` означает «никогда не выгружать». Значение `0` — выгрузить сразу после ответа.

**В Docker Compose:** модель загружается в VRAM при warm-up и остаётся там,
пока контейнер запущен. В `docker-compose.yml` можно добавить:

```yaml
environment:
  - OLLAMA_KEEP_ALIVE=-1
```

---

### Баг #5 — DRY_RUN=false на Windows: `luac: command not found`

**Симптом:**

```
FileNotFoundError: [WinError 2] Не удается найти указанный файл: 'luac'
```

**Причина:**

`luac` (компилятор Lua, используемый для синтаксической проверки) не входит
в стандартную поставку Windows. При `DRY_RUN=false` `validator.py` пытается его запустить.

**Решение:**

```powershell
$env:DRY_RUN = "true"
```

При `DRY_RUN=true` валидатор пропускает проверку и всегда возвращает `valid=True`.
Retry-loop всё ещё работает, но не по причине синтаксических ошибок.

В Docker-контейнере `lua5.4` установлен через `apt-get` в Dockerfile,
и `DRY_RUN=false` работает корректно.

---

## 6. Быстрая диагностическая шпаргалка

```
Проблема                                       Вероятная причина          Раздел
───────────────────────────────────────────────────────────────────────────────
Модель "не понимает русский"               →   Баг #1 (PS 5.1 + ASCII)    §5.1
502 Bad Gateway при запросах Python        →   Баг #2 (системный прокси)  §5.2
ModuleNotFoundError test_base_cases_data   →   Баг #3 (импорт)            §5.3
Первый запрос после паузы очень медленный  →   Баг #4 (KEEP_ALIVE)        §5.4
luac: command not found на Windows         →   Баг #5 (DRY_RUN)           §5.5
Ollama не отвечает изнутри Docker          →   Адрес должен быть ollama:11434, не localhost
API отвечает task_id, а «кода нет»       →   Смотри SSE до stage done; в POST /generate кода нет
API / SSE ok, но code пустой             →   CoT-парсер не нашёл тег <code>
                                               Проверь system_prompt.txt
Warm-up занимает больше 30 секунд          →   Модель не скачана или повреждена
                                               docker-compose run --rm ollama ollama list
```

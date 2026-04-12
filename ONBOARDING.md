# ONBOARDING.md — Введение в проект

Добро пожаловать в проект **LocalScript** (Трек 2, True Tech Hack 2026).

Этот документ поможет понять проект с самых основ, даже если у вас нет предварительных знаний о нём. Читай сверху вниз.

---

## Что мы строим и зачем

### Контекст: платформа MWS Octapi LowCode

[MWS Octapi](https://mws.ru) — корпоративная платформа для автоматизации бизнес-процессов.
Бизнес-аналитики создают в ней «сценарии» (workflows): последовательности шагов,
ветки условий, циклы. Каждый шаг может выполнять Lua-код — небольшой скрипт,
который что-то делает с данными процесса.

Данные рабочего процесса живут в объекте `wf.vars`. Например:
- `wf.vars.orders` — список заказов
- `wf.vars.userName` — имя пользователя
- `wf.initVariables.maxRetries` — параметр инициализации

Проблема: аналитики не умеют программировать. Им нужно описать задачу словами,
а получить готовый Lua-код.

### Что делает LocalScript

LocalScript — HTTP API. Принимает текстовую задачу, возвращает Lua-код:

```
Запрос:  {"prompt": "отфильтровать заказы со статусом 'выполнен'"}
Ответ:   {"code": "local result = _utils.array.new()
for _, o in ipairs(wf.vars.orders) do
  if o.status == 'выполнен' then
    table.insert(result, o)
  end
end
return result"}
```

### Почему нельзя обойтись шаблонами или поиском по базе?

Разные люди описывают одно и то же по-разному:

| Что написал аналитик | Что он хочет |
|---|---|
| «оставить только выполненные заказы» | filter(orders, status == "выполнен") |
| «убрать из списка незавершённые заявки» | filter(orders, status == "выполнен") |
| «выбрать orders где status = done» | filter(orders, status == "выполнен") |

Шаблон ищет точное совпадение — не найдёт ни одного из трёх.
[LLM (Large Language Model)](https://ru.wikipedia.org/wiki/Большая_языковая_модель) понимает
**смысл** запроса, а не его буквальную форму. Поэтому здесь нужна языковая модель.

### Почему система работает локально (без облака)?

Задание хакатона явно требует: решение должно работать на локальной инфраструктуре
без внешних API-вызовов. Мы используем [Ollama](https://ollama.com) — инструмент
для запуска open-source LLM на собственном железе, и модель
[Qwen2.5-Coder](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct) от Alibaba,
которая специализируется на генерации кода.

---

## Как устроена система (кратко)

```
ТЫ / платформа MWS
      │
      │  POST http://localhost:8080/generate
      │  {"prompt": "..."}
      ▼
FastAPI (uvicorn, порт 8080)   ← твой Python-код
      │
      │  собирает промпт из 20 примеров + запрос
      │  отправляет в Ollama
      ▼
Ollama (порт 11434)            ← отдельный процесс, запускает LLM на GPU
      │
      │  генерирует текст по промпту
      ▼
FastAPI снова
      │  извлекает <code>...</code> из ответа
      │  проверяет синтаксис через luac
      │  если ошибка — повторяет (макс. 3 раза)
      ▼
{"code": "return wf.vars..."}
```

**Ollama** — это как «драйвер для GPU + сервер моделей». Он загружает веса LLM
в видеопамять (VRAM) и отвечает на HTTP-запросы. Подробнее: [ollama.com/docs](https://ollama.com/docs).

**FastAPI** — Python-фреймворк для HTTP API. Подробнее: [fastapi.tiangolo.com](https://fastapi.tiangolo.com/ru/).

**Chain-of-Thought (CoT)** — техника промптинга: модели предлагают сначала написать
рассуждение, а потом код. Это улучшает качество. Подробнее:
[Wei et al., 2022](https://arxiv.org/abs/2201.11903).

**Few-shot prompting** — в промпт добавляют примеры «вопрос→ответ», чтобы модель
поняла нужный формат. У нас 20 примеров в `prompts/system_prompt.txt`.
Подробнее: [Prompt Engineering Guide](https://www.promptingguide.ai/ru/techniques/fewshot).

---

## Структура репозитория — что где лежит

```
task-repo/
│
├── README.md
│   Техническая документация проекта на русском. Архитектура C1/C2/C3,
│   инструкция по запуску (Docker + Windows), переменные среды, troubleshooting.
│
├── ONBOARDING.md              ← этот файл
│   Введение. Объясняет зачем, что и как — от основ до архитектуры.
│
├── Dockerfile
│   Описывает Docker-образ для Python API.
│   Подробнее про Docker: https://docs.docker.com/get-started/
│
├── docker-compose.yml
│   Запускает два контейнера вместе: api и ollama.
│   Подробнее: https://docs.docker.com/compose/
│
├── requirements.txt
│   Зависимости Python: fastapi, uvicorn, pydantic, httpx.
│
├── api/
│   Весь Python-код сервиса.
│   ├── main.py                ← Точка входа FastAPI.
│   ├── models.py              ← Pydantic-модели (схемы запросов/ответов).
│   ├── agent.py               ← Главный оркестратор (OllamaClient, CoT-парсер, логика ретраев).
│   ├── validator.py           ← LuaValidator (проверка кода через luac).
│   └── prompt_builder.py      ← Сборка промпта для LLM.
│
├── prompts/
│   └── system_prompt.txt
│       САМЫЙ ВАЖНЫЙ ФАЙЛ ДЛЯ КАЧЕСТВА ГЕНЕРАЦИИ.
│       Содержит инструкции и 20 few-shot примеров для модели. Изменение этого файла — 
│       главный рычаг улучшения точности системы.
│
└── tests/
    Папка со всеми тестами системы и отчетами.
    ├── test_base_cases_data.py
    │   Единый словарь (источник правды). Содержит эталонные примеры (ожидаемый Lua-код)
    │   и по 5 вариантов перефразированных запросов на каждый случай.
    │
    ├── test_base_cases.py
    │   Главный тест-раннер (на базе unittest).
    │   - Прогоняет все промпты через локальный API.
    │   - Сравнивает ответ с эталоном.
    │   - Выводит красивый прогресс в консоль.
    │   - Генерирует Markdown и JSON отчёты.
    │
    └── reports/
        Сюда автоматически сохраняются результаты прогона тестов (.md, .json). 
        Добавлено в .gitignore.
```

---

## Как запустить (кратко)

### Docker (рекомендуется, работает на Windows/Linux/Mac):
```bash
docker-compose run --rm ollama ollama pull qwen2.5-coder:7b-instruct-q4_K_M
docker-compose up --build
curl -X POST http://localhost:8080/generate -H "Content-Type: application/json" -d '{"prompt":"получить последний email из списка"}'
```

### Windows без Docker (для разработки):
Подробная инструкция с описанием проблемы с прокси — в `README.md`.

---

## Известные особенности и подводные камни

### Системный прокси (Clash Verge, Proxifier и др.)

Если на машине включён системный прокси — Python направит все HTTP-запросы
через него, включая запросы к `localhost`. Прокси вернёт `502 Bad Gateway`.

**Решение:** `$env:NO_PROXY = "localhost,127.0.0.1,::1"` перед запуском uvicorn.
Docker Compose эта проблема не касается.

### Модель в памяти (KEEP_ALIVE)

По умолчанию Ollama выгружает модель из VRAM через 5 минут простоя.
При локальной разработке: `$env:OLLAMA_KEEP_ALIVE = "-1"` перед `ollama serve`.

### DRY_RUN на Windows

Lua-компилятор `luac` не входит в стандартную поставку Windows.
При `DRY_RUN=true` валидация пропускается — код не проверяется на синтаксис.
В Docker-контейнере `lua5.4` установлен и `DRY_RUN=false` работает корректно.

### Модель понимает только задачи MWS Octapi

Qwen2.5-Coder обучена на системном промпте с 20 примерами операций над `wf.vars.*`.
Запросы вне этой области (алгоритмы, математика, общие задачи Lua) могут дать
некорректный результат. Это ожидаемое поведение, не баг.

---

## Полезные ссылки

| Тема | Ссылка |
|---|---|
| Ollama — что это и как работает | https://ollama.com/docs |
| Qwen2.5-Coder — модель | https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct |
| FastAPI — документация | https://fastapi.tiangolo.com/ru/ |
| Few-shot prompting | https://www.promptingguide.ai/ru/techniques/fewshot |
| Chain-of-Thought prompting | https://www.promptingguide.ai/ru/techniques/cot |
| Lua 5.4 — справочник | https://www.lua.org/manual/5.4/ |
| Docker Compose | https://docs.docker.com/compose/ |
| httpx (Python HTTP клиент) | https://www.python-httpx.org/ |
| Pydantic v2 | https://docs.pydantic.dev/latest/ |

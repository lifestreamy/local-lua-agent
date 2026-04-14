# API Contract — LocalScript (v3 — Async SSE & Conversational Messages)

> Расположение в репозитории: `docs/api_contract_description.md`

Этот документ описывает HTTP API сервиса **LocalScript** — локального агента для генерации Lua-кода.
**ВНИМАНИЕ:** API переведено на асинхронную модель с Server-Sent Events (SSE). Агент теперь может не только выдавать код, но и вести диалог (задавать уточняющие вопросы).

***

## Базовый URL

```
http://localhost:8080
```

***

## Endpoints

### 1. `POST /generate`

Отправить задание в очередь на генерацию.

#### Запрос

```http
POST /generate
Content-Type: application/json; charset=utf-8
```

**Тело запроса:**

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `prompt` | `string` | ✅ | Полный ввод пользователя (вопрос + сам код, если он его вставил). Всё отправляется единым текстом. |
| `context` | `string` | ❌ | История диалога (rolling context) для мульти-turn чата. **Лимит: 4096 символов.** Если больше — фронтенд должен обрезать старые сообщения. |

**Пример запроса:**

```json
{
  "prompt": "Исправь этот код: \n```lua\nreturn 1\n```\nДобавь проверку на nil.",
  "context": "User: как создать массив?\nAssistant: используй _utils.array.new()"
}
```

#### Ответ (HTTP 200 OK)

Возвращает ID задачи для последующего поллинга через SSE.

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

***

### 2. `GET /status`

Получить поток статусов генерации (Server-Sent Events).

#### Запрос

```http
GET /status?task_id=550e8400-e29b-41d4-a716-446655440000
Accept: text/event-stream
```

#### Ответ (HTTP 200 OK — Stream)

Стримит JSON-объекты. Теперь включает поле `message` для текстовых ответов или вопросов от LLM.

**Пример 1: Успешная генерация кода с пояснением от модели**
```json
data: {"stage": "pending", "message": "", "code": "", "error": ""}
data: {"stage": "generating", "message": "Я понял задачу. Использую _utils.array.new().", "code": "", "error": ""}
data: {"stage": "validating", "message": "", "code": "", "error": ""}
data: {"stage": "done", "message": "Вот исправленный код:", "code": "local r = _utils.array.new()\nreturn r", "error": ""}
```

**Пример 2: Агент задает уточняющий вопрос (Clarification Loop)**
Если промпт непонятен, агент не генерирует код, а спрашивает детали. В этом случае `code` будет пустым.
```json
data: {"stage": "pending", "message": "", "code": "", "error": ""}
data: {"stage": "generating", "message": "", "code": "", "error": ""}
data: {"stage": "done", "message": "Уточните, пожалуйста: фильтровать только активные заказы или вообще все?", "code": "", "error": ""}
```

***

### 3. `GET /health`

Проверка доступности сервиса. (В будущем будет дополнено статусом модели и GPU для баллов).

```http
GET /health
```

**HTTP 200 OK:**

```json
{"status": "ok"}
```

***

## Важные ограничения поля `code` в итоговом ответе SSE

- Возвращается **чистый Lua** без обёртки в markdown (без `` ```lua `` и `` ``` ``).
- Должен заканчиваться оператором `return`.
- Не использует `io`, `os`, `require` и другие запрещённые библиотеки MWS Octapi.
- Все переменные рабочего процесса доступны через `wf.vars.*` и `wf.initVariables.*`.
- Массивы создаются через `_utils.array.new()`.

***

## Важная заметка для Windows-разработчиков — кодировка

**PowerShell 5.1** кодирует тело `-Body` как **ASCII**, заменяя кириллицу на `?????????`.
Используйте `curl` или Python (`httpx`) для тестов, либо явно кодируйте в UTF-8:

```bash
curl -X POST http://localhost:8080/generate \
     -H "Content-Type: application/json; charset=utf-8" \
     -d '{"prompt": "Отфильтровать выполненные заказы"}'
```

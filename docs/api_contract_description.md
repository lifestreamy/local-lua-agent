# API Contract — LocalScript

> Расположение в репозитории: `docs/api_contract_description.md`

Этот документ описывает HTTP API сервиса **LocalScript** — локального агента для генерации Lua-кода по заданию на естественном языке.

***

## Базовый URL

```
http://localhost:8080
```

***

## Endpoints

### `POST /generate`

Принять задание на естественном языке, вернуть сгенерированный Lua-код.

#### Запрос

```http
POST /generate
Content-Type: application/json; charset=utf-8
```

**Тело запроса:**

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `prompt` | `string` | ✅ | Текст задания на русском или английском языке |
| `context` | `string` | ❌ | Существующий Lua-код, который нужно дополнить или исправить |

**Пример — генерация с нуля:**

```json
{
  "prompt": "Отфильтровать заказы со статусом 'выполнен' из wf.vars.orders"
}
```

**Пример — доработка существующего кода:**

```json
{
  "prompt": "Добавить проверку: если массив пустой — вернуть nil",
  "context": "local result = _utils.array.new()\nfor _, o in ipairs(wf.vars.orders) do\n  table.insert(result, o)\nend\nreturn result"
}
```

#### Ответ

**HTTP 200 OK**

```http
Content-Type: application/json; charset=utf-8
```

| Поле | Тип | Описание |
|------|-----|----------|
| `code` | `string` | Готовый Lua-код. Чистая строка без markdown-обёрток |

**Пример ответа:**

```json
{
  "code": "local result = _utils.array.new()\nfor _, o in ipairs(wf.vars.orders) do\n  if o.status == 'выполнен' then\n    table.insert(result, o)\n  end\nend\nreturn result"
}
```

**HTTP 422 Unprocessable Entity** — некорректное тело запроса (Pydantic validation error):

```json
{
  "detail": [{"loc": ["body", "prompt"], "msg": "field required", "type": "value_error.missing"}]
}
```

**HTTP 500 Internal Server Error** — Ollama недоступен или ответил некорректно.

***

### `GET /health`

Проверка доступности сервиса.

```http
GET /health
```

**HTTP 200 OK:**

```json
{"status": "ok"}
```

***

## Важные ограничения поля `code` в ответе

- Возвращается **чистый Lua** без обёртки в markdown (без `` ```lua `` и `` ``` ``).
- Должен заканчиваться оператором `return`.
- Не использует `io`, `os`, `require` и другие запрещённые библиотеки MWS Octapi.
- Все переменные рабочего процесса доступны через `wf.vars.*` и `wf.initVariables.*`.
- Массивы создаются через `_utils.array.new()`.

***

## Важная заметка для Windows-разработчиков — кодировка

### Проблема

**PowerShell 5.1** (встроенный в Windows 10/11) кодирует тело `-Body` в Invoke-RestMethod как **ASCII**, не как UTF-8.
Кириллические символы при этом заменяются на `?????????`, и модель их не распознаёт.

### Проверка версии PowerShell

```powershell
$PSVersionTable.PSVersion
# Major = 5 → проблема с кодировкой
# Major = 7 → UTF-8 по умолчанию, проблем нет
```

### Решение для PowerShell 5.1

```powershell
# Явно кодировать тело в UTF-8 байты перед отправкой:
$json = '{"prompt": "Привет, сгенерируй код"}'
$bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
Invoke-RestMethod -Uri http://localhost:8080/generate `
    -Method POST `
    -ContentType "application/json; charset=utf-8" `
    -Body $bytes
```

### Решение через файл

```powershell
# Сохранить тело в файл UTF-8 без BOM, передать как -InFile:
$json = '{"prompt": "Привет, сгенерируй код"}' | Out-File -Encoding utf8NoBOM body.json
Invoke-RestMethod -Uri http://localhost:8080/generate `
    -Method POST `
    -ContentType "application/json; charset=utf-8" `
    -InFile body.json
```

### Решение для curl (всегда работает):

```bash
curl -X POST http://localhost:8080/generate \
     -H "Content-Type: application/json; charset=utf-8" \
     -d '{"prompt": "Отфильтровать выполненные заказы"}'
```

***

## Примеры использования

### curl (Linux / macOS / Git Bash)

```bash
# Базовый запрос
curl -X POST http://localhost:8080/generate \
     -H "Content-Type: application/json" \
     -d '{"prompt": "Получить последний email из wf.vars.emails"}'

# С передачей контекста
curl -X POST http://localhost:8080/generate \
     -H "Content-Type: application/json" \
     -d '{"prompt": "Добавить фильтрацию пустых значений", "context": "return wf.vars.items"}'
```

### Python (httpx)

```python
import httpx

r = httpx.post("http://localhost:8080/generate", json={
    "prompt": "Отфильтровать заказы со статусом выполнен"
})
print(r.json()["code"])
```

### PowerShell 5.1 (с корректной кодировкой UTF-8)

```powershell
$json = '{"prompt": "Получить последний email из массива"}'
$bytes = [System.Text.Encoding]::UTF8.GetBytes($json)
$response = Invoke-RestMethod -Uri http://localhost:8080/generate `
    -Method POST `
    -ContentType "application/json; charset=utf-8" `
    -Body $bytes
Write-Host $response.code
```

### PowerShell 7+ (pwsh)

```powershell
# Работает напрямую — UTF-8 по умолчанию с PS 7.4+
Invoke-RestMethod -Uri http://localhost:8080/generate `
    -Method POST `
    -ContentType "application/json; charset=utf-8" `
    -Body '{"prompt": "Получить последний email из массива"}'
```

***

## OpenAPI-совместимость

Базовая схема контракта (`openapi.yaml`) находится в корне репозитория.
Контракт расширяем: допустимо добавлять поля и endpoints при условии сохранения обратной совместимости с базовым `POST /generate`.
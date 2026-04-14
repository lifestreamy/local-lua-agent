# API Context Formatting Contract (v1.1)

To prevent **Context Poisoning** and **Prompt Injection**, all clients (Web UI, CLI) MUST format the `context` field according to these strict rules. The API endpoint (`POST /generate`) remains unchanged, but the *contents* of the `context` string must follow this standard.

## 1. The Rule of Semantic History
The `context` field must ONLY contain purely semantic history.
It MUST NOT contain:
- System status messages (e.g., "Проверка безопасности...", "Попытка 1 из 3...").
- Internal validation errors or stack traces.
- Security block messages (e.g., `return nil -- [SECURITY_BLOCK]...`).

## 2. Formatting Mixed Responses (Text + Code)
The SSE stream returns both `message` (text) and `code` (Lua). A single assistant turn often contains both. Clients MUST combine them using standard Markdown formatting so the LLM guard correctly parses what was conversational and what was code.

### Standard Format Template:
```text
User: [USER_PROMPT]
Assistant: [MESSAGE_FROM_SSE]
```lua
[CODE_FROM_SSE]
```
```

*(Note: If `message` is empty, omit the Assistant text line. If `code` is empty, omit the markdown code block).*

## 3. Example of a Multi-Turn Context String

**What the client sends in the `context` JSON field:**

```text
User: Создай массив и добавь 1 и 2
Assistant: Я создал массив и добавил нужные элементы.
```lua
local r = _utils.array.new()
table.insert(r, 1)
table.insert(r, 2)
return r
```
User: Ой, я имел в виду добавить 3 и 4
Assistant: Понял, исправляю элементы на 3 и 4. Уточните, нужен ли возврат nil при ошибке?
```

## 4. Backend Processing (Invisible to Client)
The backend takes your properly formatted `context` string and securely sandwiches it in XML tags to prevent hijacking:
```xml
<chat_history>
[YOUR STRICTLY FORMATTED CONTEXT STRING]
</chat_history>

<user_input>
[NEW PROMPT HERE]
</user_input>
```

"""
Вызов локальной модели Ollama через HTTP (REST), только стандартная библиотека Python.
Требуется: запущенный Ollama и модель qwen2.5-coder:7b-instruct-q4_K_M
(ollama pull qwen2.5-coder:7b-instruct-q4_K_M).
"""

import json
import sys
import urllib.error
import urllib.request
from typing import Optional

OLLAMA_HOST = "http://localhost:11434"
MODEL = "qwen2.5-coder:7b-instruct-q4_K_M"
CHAT_URL = f"{OLLAMA_HOST}/api/chat"


def chat_stream(
    user_message: str,
    *,
    system: Optional[str] = "Ты — помощник по программированию. Отвечай кратко и по делу.",
) -> None:
    """Отправляет запрос в /api/chat и печатает ответ потоком (как в интерактивном ollama run)."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user_message})

    payload = {"model": MODEL, "messages": messages, "stream": True}
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        CHAT_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=300) as response:
            for raw_line in response:
                line = raw_line.strip()
                if not line:
                    continue
                data = json.loads(line.decode("utf-8"))
                chunk = data.get("message", {}).get("content", "")
                if chunk:
                    print(chunk, end="", flush=True)
                if data.get("done"):
                    break
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"HTTP-ошибка: {e.code} — {err_body}", file=sys.stderr)
        raise SystemExit(1) from e
    except urllib.error.URLError as e:
        print(
            "Не удалось подключиться к Ollama на localhost:11434.\n"
            "Запустите сервер (обычно достаточно запустить приложение Ollama или `ollama serve`).",
            file=sys.stderr,
        )
        raise SystemExit(1) from e

    print()


def main() -> None:
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:]).strip()
    else:
        question = input("Вопрос модели: ").strip()

    if not question:
        print("Пустой вопрос.", file=sys.stderr)
        raise SystemExit(1)

    chat_stream(question)


if __name__ == "__main__":
    main()

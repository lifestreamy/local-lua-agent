import asyncio
import json
import httpx

BASE_URL = "http://localhost:8080"

async def test_session():
    print("=============================================")
    print(" MULTI-TURN LOCAL TEST SCRIPT (4 TURNS) ")
    print("=============================================\n")

    prompts = [
        "Создай пустой массив с _utils.array.new()",
        "Добавь в него число 5",
        "А теперь добавь еще число 10",
        "Сделай так, чтобы функция возвращала только первый элемент"
    ]

    history = ""

    async with httpx.AsyncClient(timeout=30.0) as client:
        for i, prompt in enumerate(prompts, start=1):
            print(f"\\n[TURN {i}]")
            print(f"Context String before request:\\n{'-'*20}\\n{history if history else '(empty)'}\\n{'-'*20}")
            print(f"Sending prompt: '{prompt}'")

            payload = {"prompt": prompt, "context": history}

            try:
                resp = await client.post(f"{BASE_URL}/generate", json=payload)
                resp.raise_for_status()
                task_id = resp.json()["task_id"]

                print(f"Task ID: {task_id}. Polling SSE...")

                current_code = ""
                current_msg = ""
                is_blocked = False

                async with client.stream("GET", f"{BASE_URL}/status?task_id={task_id}") as stream:
                    async for line in stream.aiter_lines():
                        if line.startswith("data: "):
                            data = json.loads(line[6:])
                            if "[SECURITY_BLOCK]" in data.get("code", ""):
                                is_blocked = True
                            if data.get("stage") == "done":
                                current_code = data.get("code", "")
                                current_msg = data.get("message", "")
                                break

                if is_blocked:
                    print(f"\\n❌ FAILED: Turn {i} was blocked by the Guard!")
                    # return # stop the test
                else:
                    print(f"\\n✅ SUCCESS: Turn {i} passed the Guard!")
                    print(f"Msg: {current_msg}\\nCode:\\n{current_code.strip()}")

                    # Build strict contract context for next turn
                    history += f"User: {prompt}\\n"
                    if current_msg:
                        history += f"Assistant: {current_msg}\\n"
                    if current_code:
                        history += f"```lua\\n{current_code}\\n```\\n"

            except Exception as e:
                print(f"Connection failed: {e}")
                return

if __name__ == "__main__":
    asyncio.run(test_session())

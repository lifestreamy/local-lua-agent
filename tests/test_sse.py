import httpx
import asyncio
import json
import sys

API_URL = "http://localhost:8080"

async def test_backend():
    print("1. Submitting prompt to /generate...")

    # Send the POST request
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{API_URL}/generate",
                json={"prompt": "Напиши простой код: local a = 1 return a"},
                timeout=10.0
            )
            resp.raise_for_status()
            data = resp.json()
            task_id = data.get("task_id")
            print(f"✅ Success! Received task_id: {task_id}\n")
        except Exception as e:
            print(f"❌ Failed to reach POST /generate: {e}")
            sys.exit(1)

    print("2. Connecting to SSE stream /status...")

    # Connect to the SSE stream
    async with httpx.AsyncClient() as client:
        try:
            async with client.stream("GET", f"{API_URL}/status", params={"task_id": task_id}, timeout=120.0) as response:
                print(f"Connected! HTTP Status: {response.status_code}\n")
                print("--- STREAM START ---")

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        # Parse the JSON payload inside the SSE data chunk
                        json_str = line.removeprefix("data: ")
                        payload = json.loads(json_str)

                        stage = payload.get("stage")
                        msg = payload.get("message", "")
                        code = payload.get("code", "")

                        print(f"[{stage.upper()}] Message: '{msg}' | Code len: {len(code)}")

                        if stage in ("done", "error"):
                            print("\n--- FINAL CODE ---")
                            print(code)
                            break

                print("--- STREAM END ---")
        except Exception as e:
            print(f"❌ Failed to read stream: {e}")

if __name__ == "__main__":
    asyncio.run(test_backend())

import asyncio
import json
import sys
import httpx
import os

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich import box

# NEW: Import prompt_toolkit for command history and up/down arrow support
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style

# Make sure we use UTF-8 on Windows for Rich
sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://localhost:8080"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b-instruct-q4_K_M")
OLLAMA_NUM_CTX = os.getenv("OLLAMA_NUM_CTX", "3072")

console = Console()

# Set up the prompt_toolkit session with in-memory history
# The 'ansigreen' style matches the [bold green] from rich
style = Style.from_dict({
    'prompt': 'ansigreen bold',
})
session = PromptSession(history=InMemoryHistory(), style=style)

def print_pinned_header():
    os.system('cls' if os.name == 'nt' else 'clear')

    text = (
        f"[bold cyan]🚀 LocalScript Interactive CLI (Hackathon Edition)[/bold cyan]\n"
        f"[dim white]Model: {OLLAMA_MODEL} | Context Limit: {OLLAMA_NUM_CTX} chars[/dim white]\n"
        f"[dim white]Leader: Tim Korelov @timkore @lifestreamy\nCo-leader: Alina Garaeva @swwerell[/dim white]\n"
        f"[italic yellow]Type 'exit' to quit | 'clear' to wipe context[/italic yellow]"
    )
    console.print(Panel(text, style="blue", box=box.ROUNDED, expand=False))
    print()

async def main():
    print_pinned_header()

    history = ""

    async with httpx.AsyncClient(timeout=120.0) as client:
        while True:
            try:
                # FIXED: Replaced console.input with prompt_toolkit session for up/down arrow history
                prompt = await session.prompt_async([('class:prompt', 'You >>> ')])
            except (EOFError, KeyboardInterrupt):
                break

            if prompt.strip().lower() == 'exit':
                break
            if prompt.strip().lower() == 'clear':
                history = ""
                print_pinned_header()
                console.print("[italic dim yellow]System: Rolling context cleared.[/italic dim yellow]\n")
                continue
            if not prompt.strip():
                continue

            payload = {"prompt": prompt, "context": history}

            try:
                resp = await client.post(f"{BASE_URL}/generate", json=payload)
                resp.raise_for_status()
                task_id = resp.json()["task_id"]
            except Exception as e:
                console.print(f"[bold red]Error:[/bold red] Failed to connect to backend: {e}\n")
                continue

            current_code = ""
            current_msg = ""

            with console.status("[bold cyan]Agent is thinking...", spinner="dots") as status:
                try:
                    async with client.stream("GET", f"{BASE_URL}/status?task_id={task_id}") as r:
                        async for line in r.aiter_lines():
                            if line.startswith("data: "):
                                data_str = line[6:]
                                try:
                                    data = json.loads(data_str)
                                    stage = data.get("stage")
                                    msg = data.get("message", "")
                                    code = data.get("code", "")
                                    err = data.get("error", "")

                                    if stage == "validating":
                                        status.update("[bold magenta]Validating syntax (luac)...")
                                    elif stage == "retrying":
                                        status.update("[bold yellow]Syntax error found, retrying...")

                                    if err:
                                        console.print(f"[bold red]Validation Error:[/bold red] {err}")

                                    if stage == "done":
                                        if msg:
                                            current_msg = msg
                                        if code:
                                            current_code = code
                                except json.JSONDecodeError:
                                    pass
                except Exception as e:
                    console.print(f"[bold red]Error:[/bold red] SSE Stream interrupted: {e}\n")

            if current_msg:
                console.print(f"\n[bold blue]LocalScript >>>[/bold blue] {current_msg}")

            if current_code:
                if "[SECURITY_BLOCK]" in current_code:
                    console.print("[bold red blink]System:[/bold red blink] Request blocked. Context not updated.\n")
                else:
                    md = Markdown(f"```lua\n{current_code}\n```")
                    console.print(Panel(md, title="[bold green]Generated Code[/bold green]", border_style="green", expand=False, box=box.ROUNDED))

            print()

            if current_code and "[SECURITY_BLOCK]" in current_code:
                pass
            else:
                history += f"User: {prompt}\n"
                if current_msg:
                    history += f"Assistant: {current_msg}\n"
                if current_code:
                    history += f"```lua\n{current_code}\n```\n"

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[dim]Exiting...[/dim]")
        sys.exit(0)
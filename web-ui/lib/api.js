const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8080";

function parseSseChunk(buffer, onEvent) {
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";
  for (const part of parts) {
    const lines = part.split("\n");
    let eventName = "message";
    let data = "";
    for (const line of lines) {
      if (line.startsWith("event:")) eventName = line.slice(6).trim();
      if (line.startsWith("data:")) data += line.slice(5).trim();
    }
    if (!data) continue;
    try {
      onEvent(eventName, JSON.parse(data));
    } catch {
      onEvent(eventName, { text: data });
    }
  }
  return rest;
}

export async function generateWithSseReady({
  prompt,
  context,
  signal,
  onStatus,
  onCodeChunk,
}) {
  onStatus("pending");
  const response = await fetch(`${API_BASE}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, context }),
    signal,
  });

  if (!response.ok) {
    let detail = "Ошибка запроса к API";
    try {
      const err = await response.json();
      detail = err.detail || detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("text/event-stream") && response.body) {
    onStatus("generating");
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      buffer = parseSseChunk(buffer, (event, payload) => {
        if (event === "status" && payload.status) onStatus(payload.status);
        if (event === "token" && payload.text) onCodeChunk(payload.text);
      });
    }
    onStatus("done");
    return;
  }

  // Fallback for current sync backend JSON response.
  onStatus("generating");
  const data = await response.json();
  onStatus("validating");
  onCodeChunk(data.code || "");
  onStatus("done");
}

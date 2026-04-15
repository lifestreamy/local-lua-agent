const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8080";
const DEBUG_API = true;

function apiDebug(event, payload = {}) {
  if (!DEBUG_API) return;
  console.log(`[API DEBUG] ${event}`, payload);
}

function normalizePhase(status) {
  const s = String(status || "").toLowerCase();
  if (!s) return "pending";
  if (["pending", "queued", "accepted"].includes(s)) return "pending";
  if (["generating", "streaming", "thinking"].includes(s)) return "generating";
  if (["validating", "validation"].includes(s)) return "validating";
  if (["retrying", "retry"].includes(s)) return "retrying";
  if (["done", "completed", "success"].includes(s)) return "done";
  if (["error", "failed", "failure"].includes(s)) return "error";
  if (["cancelled", "canceled"].includes(s)) return "cancelled";
  return s;
}

function parseSseChunk(buffer, onEvent) {
  const normalized = buffer.replace(/\r\n/g, "\n");
  const parts = normalized.split("\n\n");
  const rest = parts.pop() ?? "";
  for (const part of parts) {
    const lines = part.split("\n");
    let eventName = "message";
    const dataLines = [];
    for (const line of lines) {
      if (line.startsWith("event:")) eventName = line.slice(6).trim();
      if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
    }
    const data = dataLines.join("\n");
    if (!data) continue;
    try {
      onEvent(eventName, JSON.parse(data));
    } catch {
      onEvent(eventName, { text: data });
    }
  }
  return rest;
}

function formatStatusEvent(payload) {
  return {
    phase: normalizePhase(payload?.phase || payload?.status || payload?.stage),
    message: payload?.message || "",
    progress:
      typeof payload?.progress === "number" ? Math.max(0, Math.min(100, payload.progress)) : null,
    ts: payload?.ts || new Date().toISOString(),
  };
}

async function streamTaskStatus({
  taskId,
  signal,
  onStatus,
  onCodeChunk,
  onAssistantMessage,
  onTimelineEvent,
}) {
  const statusUrl = `${API_BASE}/status?task_id=${encodeURIComponent(taskId)}`;
  apiDebug("sse:connect_start", { statusUrl, taskId });
  const response = await fetch(statusUrl, {
    headers: { Accept: "text/event-stream" },
    signal,
  });
  if (!response.ok || !response.body) {
    apiDebug("sse:connect_error", { status: response.status });
    throw new Error(`SSE недоступен (${response.status})`);
  }
  apiDebug("sse:connected", { status: response.status });
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  const handleParsedEvent = (event, payload) => {
    apiDebug("sse:event", { event, payload });
    if (event === "status" || event === "message") {
      const statusEvent = formatStatusEvent(payload);
      onStatus(statusEvent.phase);
      onTimelineEvent?.(statusEvent);
      if (
        statusEvent.phase === "done" &&
        typeof payload?.message === "string" &&
        payload.message.trim()
      ) {
        onAssistantMessage?.(payload.message);
      }
      if (typeof payload?.code === "string" && payload.code) {
        onCodeChunk(payload.code);
      }
    }
    if (event === "token" && payload?.text) {
      onCodeChunk(payload.text);
    }
    if (event === "done") {
      const statusEvent = formatStatusEvent({
        phase: "done",
        message: payload?.message || "Готово",
        progress: 100,
        ts: payload?.ts,
      });
      onStatus("done");
      onTimelineEvent?.(statusEvent);
      if (typeof payload?.message === "string" && payload.message.trim()) {
        onAssistantMessage?.(payload.message);
      }
      if (typeof payload?.code === "string" && payload.code) {
        onCodeChunk(payload.code);
      } else if (payload?.result?.code) {
        onCodeChunk(payload.result.code);
      }
    }
    if (event === "error") {
      onStatus("error");
      onTimelineEvent?.(
        formatStatusEvent({
          phase: "error",
          message: payload?.message || "Ошибка на стороне сервера",
          progress: null,
          ts: payload?.ts,
        })
      );
    }
  };
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    apiDebug("sse:chunk_raw", { bytes: value?.length || 0 });
    buffer += decoder.decode(value, { stream: true });
    buffer = parseSseChunk(buffer, handleParsedEvent);
  }
  // Flush tail event if server closed stream without final blank line.
  if (buffer.trim()) {
    apiDebug("sse:flush_tail_buffer", { bytes: buffer.length });
    parseSseChunk(`${buffer}\n\n`, handleParsedEvent);
  }
}

export async function generateWithSseReady({
  prompt,
  context,
  signal,
  onStatus,
  onCodeChunk,
  onAssistantMessage,
  onTimelineEvent,
}) {
  apiDebug("generate:start", {
    apiBase: API_BASE,
    promptLength: String(prompt || "").length,
    contextLength: String(context || "").length,
  });
  // Точное содержимое полей JSON тела POST /generate (для сравнения 1-го и 2-го запроса в DevTools).
  apiDebug("generate:wire_payload", { prompt, context });
  onStatus("pending");
  onTimelineEvent?.({
    phase: "pending",
    message: "Запрос отправлен",
    progress: null,
    ts: new Date().toISOString(),
  });

  const response = await fetch(`${API_BASE}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, context }),
    signal,
  });
  apiDebug("generate:response_headers", {
    status: response.status,
    contentType: response.headers.get("content-type") || "",
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

  // Legacy sync backend (current contract): direct code response.
  if (contentType.includes("application/json")) {
    const data = await response.json();
    apiDebug("generate:json_payload", data || {});
    if (typeof data?.code === "string") {
      onStatus("generating");
      onTimelineEvent?.(
        formatStatusEvent({ phase: "generating", message: "Генерирую код..." })
      );
      onStatus("validating");
      onTimelineEvent?.(
        formatStatusEvent({ phase: "validating", message: "Проверяю ответ..." })
      );
      onCodeChunk(data.code || "");
      onStatus("done");
      onTimelineEvent?.(
        formatStatusEvent({ phase: "done", message: "Готово", progress: 100 })
      );
      return;
    }

    // SSE-ready backend: /generate returns task_id
    const taskId = data?.task_id || data?.request_id || data?.id;
    if (!taskId) {
      throw new Error("Ответ /generate не содержит code или task_id");
    }
    onTimelineEvent?.(
      formatStatusEvent({
        phase: "pending",
        message: `Создан task_id: ${taskId}`,
      })
    );
    onTimelineEvent?.(
      formatStatusEvent({
        phase: "pending",
        message: "Подключаюсь к SSE /status",
      })
    );
    await streamTaskStatus({
      taskId,
      signal,
      onStatus,
      onCodeChunk,
      onAssistantMessage,
      onTimelineEvent,
    });
    return;
  }

  // If /generate itself starts streaming directly.
  if (contentType.includes("text/event-stream") && response.body) {
    apiDebug("generate:direct_sse_stream");
    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      apiDebug("generate:direct_sse_chunk_raw", { bytes: value?.length || 0 });
      buffer += decoder.decode(value, { stream: true });
      buffer = parseSseChunk(buffer, (event, payload) => {
        apiDebug("generate:direct_sse_event", { event, payload });
        if (event === "status" || event === "message") {
          const statusEvent = formatStatusEvent(payload);
          onStatus(statusEvent.phase);
          onTimelineEvent?.(statusEvent);
        }
        if (event === "token" && payload?.text) onCodeChunk(payload.text);
      });
    }
    onStatus("done");
    onTimelineEvent?.(
      formatStatusEvent({ phase: "done", message: "Поток завершен", progress: 100 })
    );
  }
}

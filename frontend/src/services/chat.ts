import { ApiError } from "../api/client";
export type StreamEvent = { event: string; data: Record<string, unknown> };
const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api";
export async function streamChat(
  conversationId: string,
  message: string,
  documentIds: string[],
  signal: AbortSignal,
  onEvent: (e: StreamEvent) => void,
) {
  const request = () => fetch(`${BASE}/chat/stream`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      conversation_id: conversationId,
      message,
      document_ids: documentIds,
    }),
    signal,
  });
  let response = await request();
  if (response.status === 401) {
    const refresh = await fetch(`${BASE}/auth/refresh`, {
      method: "POST", credentials: "include", signal,
    });
    if (refresh.ok) response = await request();
  }
  if (!response.ok) throw new ApiError("Unable to start generation.", response.status);
  if (!response.body) throw Error("Streaming is unavailable.");
  const reader = response.body.getReader(),
    decoder = new TextDecoder();
  let buffer = "", completed = false;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const packets = buffer.split("\n\n");
      buffer = packets.pop() || "";
      for (const packet of packets) {
        let event = "message",
          data = "{}";
        for (const line of packet.split("\n")) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          if (line.startsWith("data:")) data = line.slice(5).trim();
        }
        if (event === "complete") completed = true;
        onEvent({ event, data: JSON.parse(data) });
      }
    }
    if (!completed) throw Error("The response stream ended before completion.");
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

export type StreamEvent = { event: string; data: Record<string, unknown> };
const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api";
export async function streamChat(
  conversationId: string,
  message: string,
  signal: AbortSignal,
  onEvent: (e: StreamEvent) => void,
) {
  const response = await fetch(`${BASE}/chat/stream`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ conversation_id: conversationId, message }),
    signal,
  });
  if (!response.ok) throw Error("Unable to start generation.");
  if (!response.body) throw Error("Streaming is unavailable.");
  const reader = response.body.getReader(),
    decoder = new TextDecoder();
  let buffer = "";
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
      onEvent({ event, data: JSON.parse(data) });
    }
  }
}

import { api } from "../api/client";
import type { AgentRun } from "../types/agent";
import { ApiError } from "../api/client";

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api";
export type AgentStreamEvent = { event: string; data: Record<string, unknown> };

export async function streamAgent(conversationId: string, goal: string, documentIds: string[],
    signal: AbortSignal, onEvent: (event: AgentStreamEvent) => void): Promise<AgentRun> {
  const request = () => fetch(`${BASE}/agents/runs/stream`, {
    method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, signal,
    body: JSON.stringify({ conversation_id: conversationId, goal, document_ids: documentIds }),
  });
  let response = await request();
  if (response.status === 401) {
    const refresh = await fetch(`${BASE}/auth/refresh`, { method: "POST", credentials: "include", signal });
    if (refresh.ok) response = await request();
  }
  if (!response.ok || !response.body) throw new ApiError("Unable to start agent run.", response.status);
  const reader = response.body.getReader(), decoder = new TextDecoder();
  let buffer = "", completed: AgentRun | null = null;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const packets = buffer.split("\n\n"); buffer = packets.pop() || "";
      for (const packet of packets) {
        let event = "message", raw = "{}";
        for (const line of packet.split("\n")) {
          if (line.startsWith("event:")) event = line.slice(6).trim();
          if (line.startsWith("data:")) raw = line.slice(5).trim();
        }
        const data = JSON.parse(raw) as Record<string, unknown>;
        if (event === "error") throw new ApiError(String(data.message || "Agent run failed."), 502);
        if (event === "complete") completed = data.run as AgentRun;
        onEvent({ event, data });
      }
    }
    if (!completed) throw Error("The agent stream ended before completion.");
    return completed;
  } finally {
    await reader.cancel().catch(() => {}); reader.releaseLock();
  }
}

export const agents = {
  create: (conversationId: string, goal: string, documentIds: string[]) => api<AgentRun>("/agents/runs", {
    method: "POST",
    body: JSON.stringify({ conversation_id: conversationId, goal, document_ids: documentIds }),
  }),
  list: (conversationId?: string) => api<AgentRun[]>(`/agents/runs${conversationId ? `?conversation_id=${encodeURIComponent(conversationId)}` : ""}`),
  get: (id: string) => api<AgentRun>(`/agents/runs/${id}`),
  resume: (id: string) => api<AgentRun>(`/agents/runs/${id}/resume`, { method: "POST", body: "{}" }),
  cancel: (id: string) => api<AgentRun>(`/agents/runs/${id}/cancel`, { method: "POST", body: "{}" }),
};

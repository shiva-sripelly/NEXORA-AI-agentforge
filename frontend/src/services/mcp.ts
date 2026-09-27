import { api } from "../api/client";
import type { Approval, MCPConnection, MCPTool, ToolCall } from "../types/mcp";

export const mcp = {
  connections: () => api<MCPConnection[]>("/mcp/connections"),
  add: (server_type: "analytics" | "file", name?: string) => api<MCPConnection>("/mcp/connections", {
    method: "POST", body: JSON.stringify({ server_type, name }),
  }),
  removeConnection: (id: string) => api<void>(`/mcp/connections/${id}`, { method: "DELETE" }),
  connect: (id: string) => api<MCPTool[]>(`/mcp/connections/${id}/connect`, { method: "POST", body: "{}" }),
  refresh: (id: string) => api<MCPTool[]>(`/mcp/connections/${id}/refresh-tools`, { method: "POST", body: "{}" }),
  tools: () => api<MCPTool[]>("/mcp/tools"),
  updateTool: (id: string, patch: { is_enabled?: boolean; requires_approval?: boolean; approval_mode?: MCPTool["approval_mode"]; risk_level?: MCPTool["risk_level"] }) => api<MCPTool>(`/mcp/tools/${id}`, {
    method: "PATCH", body: JSON.stringify(patch),
  }),
  execute: (id: string, args: Record<string, unknown>) => api<ToolCall>(`/mcp/tools/${id}/execute`, {
    method: "POST", body: JSON.stringify({ arguments: args }),
  }),
  calls: () => api<ToolCall[]>("/mcp/tool-calls"),
  approvals: (pending = true) => api<Approval[]>(`/mcp/approvals?pending=${pending}`),
  approval: (id: string) => api<Approval>(`/mcp/approvals/${id}`),
  approve: (id: string, resolution_note?: string) => api<ToolCall>(`/mcp/approvals/${id}/approve`, {
    method: "POST", body: JSON.stringify({ resolution_note: resolution_note || null }),
  }),
  deny: (id: string, resolution_note?: string) => api<ToolCall>(`/mcp/approvals/${id}/deny`, {
    method: "POST", body: JSON.stringify({ resolution_note: resolution_note || null }),
  }),
};

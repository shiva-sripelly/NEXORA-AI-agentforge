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
  updateTool: (id: string, patch: { is_enabled?: boolean; requires_approval?: boolean }) => api<MCPTool>(`/mcp/tools/${id}`, {
    method: "PATCH", body: JSON.stringify(patch),
  }),
  execute: (id: string, args: Record<string, unknown>) => api<ToolCall>(`/mcp/tools/${id}/execute`, {
    method: "POST", body: JSON.stringify({ arguments: args }),
  }),
  calls: () => api<ToolCall[]>("/mcp/tool-calls"),
  approvals: () => api<Approval[]>("/mcp/approvals?pending=true"),
  approve: (id: string) => api<ToolCall>(`/mcp/approvals/${id}/approve`, { method: "POST", body: "{}" }),
  deny: (id: string) => api<ToolCall>(`/mcp/approvals/${id}/deny`, { method: "POST", body: "{}" }),
};

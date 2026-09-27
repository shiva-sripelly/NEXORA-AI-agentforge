import type { MCPTool } from "./mcp";

export type GovernanceTool = MCPTool;
export type ToolPolicy = {
  id: string; tool_id: string; tool_name: string; user_id: string | null; role: "USER" | "ADMIN" | null;
  effect: "allow" | "deny"; approval_mode: "never" | "always" | "risk_based" | null;
  created_at: string; updated_at: string;
};
export type AuditEvent = {
  id: string; actor_user_id: string | null; event_type: string; tool_id: string | null;
  agent_run_id: string | null; approval_request_id: string | null;
  metadata: Record<string, unknown>; created_at: string;
};

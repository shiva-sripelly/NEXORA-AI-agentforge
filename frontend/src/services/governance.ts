import { api } from "../api/client";
import type { AuditEvent, GovernanceTool, ToolPolicy } from "../types/governance";

export const governance = {
  tools: () => api<GovernanceTool[]>("/governance/tools"),
  updateTool: (id: string, patch: Partial<Pick<GovernanceTool, "is_enabled" | "risk_level" | "approval_mode">>) =>
    api<GovernanceTool>(`/governance/tools/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  policies: () => api<ToolPolicy[]>("/governance/policies"),
  createPolicy: (data: { tool_id: string; user_id?: string; role?: "USER" | "ADMIN"; effect: "allow" | "deny";
      approval_mode?: "never" | "always" | "risk_based" }) =>
    api<ToolPolicy>("/governance/policies", { method: "POST", body: JSON.stringify(data) }),
  updatePolicy: (id: string, patch: Partial<Pick<ToolPolicy, "effect" | "approval_mode">>) =>
    api<ToolPolicy>(`/governance/policies/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
  removePolicy: (id: string) => api<void>(`/governance/policies/${id}`, { method: "DELETE" }),
  audit: () => api<AuditEvent[]>("/governance/audit"),
};

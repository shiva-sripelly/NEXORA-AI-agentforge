export type MCPConnection = {
  id: string; name: string; server_type: "analytics" | "file"; transport: string;
  status: "connected" | "disconnected" | "error"; is_enabled: boolean;
  created_at: string; updated_at: string;
};
export type MCPTool = {
  id: string; connection_id: string; connection_name: string; external_name: string;
  display_name: string; description: string | null; input_schema: Record<string, unknown>;
  is_enabled: boolean; requires_approval: boolean; risk_level: string;
  discovered_at: string; updated_at: string;
};
export type ToolCall = {
  id: string; conversation_id?: string | null; message_id?: string | null; mcp_tool_id?: string;
  tool_name: string; status: "pending" | "awaiting_approval" | "running" | "completed" | "failed" | "denied";
  arguments_summary: Record<string, unknown>; result_summary: string | null; error_message?: string | null;
  risk_level?: string; approval_id?: string | null; started_at?: string; completed_at?: string | null; created_at?: string;
  final_message_content?: string | null;
};
export type Approval = {
  id: string; tool_call_id: string; tool_name: string; status: string; risk_level: string;
  arguments_summary: Record<string, unknown>; requested_at: string; resolved_at: string | null;
};

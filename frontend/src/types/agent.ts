export type AgentStep = {
  id: string;
  step_number: number;
  step_type: "tool" | "rag" | "final";
  title: string;
  description: string | null;
  tool_name: string | null;
  arguments_summary: Record<string, unknown>;
  status: "pending" | "running" | "awaiting_approval" | "completed" | "failed" | "skipped" | "cancelled";
  result_summary: string | null;
  error_message: string | null;
  approval_id: string | null;
  started_at: string | null;
  completed_at: string | null;
};

export type AgentRun = {
  id: string;
  conversation_id: string | null;
  triggering_message_id: string | null;
  goal: string;
  status: "planning" | "running" | "awaiting_approval" | "completed" | "failed" | "cancelled" | "max_steps_reached";
  current_step: number;
  total_steps: number;
  max_steps: number;
  started_at: string;
  completed_at: string | null;
  failed_at: string | null;
  error_message: string | null;
  final_answer: string | null;
  created_at: string;
  updated_at: string;
  steps: AgentStep[];
};

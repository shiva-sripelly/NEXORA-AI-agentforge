import type { ToolCall } from "./mcp";

export type Conversation = {
  id: string;
  title: string;
  model_provider: string;
  model_name: string;
  created_at: string;
  updated_at: string;
};
export type Source = {
  document_id: string | null;
  document_chunk_id: string | null;
  document_name: string;
  page: number | null;
  rank: number;
  score: number;
};
export type Message = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  token_count: number | null;
  created_at: string;
  sources?: Source[];
  tool_calls?: ToolCall[];
};
export type ConversationList = {
  items: Conversation[];
  total: number;
  page: number;
  page_size: number;
};

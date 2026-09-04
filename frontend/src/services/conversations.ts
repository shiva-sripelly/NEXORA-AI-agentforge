import { api } from "../api/client";
import type { Conversation, ConversationList, Message } from "../types/chat";
export const conversations = {
  list: () => api<ConversationList>("/conversations"),
  create: () =>
    api<Conversation>("/conversations", { method: "POST", body: "{}" }),
  get: (id: string) => api<Conversation>(`/conversations/${id}`),
  messages: (id: string) => api<Message[]>(`/conversations/${id}/messages`),
  rename: (id: string, title: string) =>
    api<Conversation>(`/conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    }),
  remove: (id: string) =>
    api<void>(`/conversations/${id}`, { method: "DELETE" }),
};

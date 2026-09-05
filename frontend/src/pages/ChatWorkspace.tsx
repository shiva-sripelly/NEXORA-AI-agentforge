import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { ChatComposer } from "../components/chat/ChatComposer";
import { ConversationSidebar } from "../components/chat/ConversationSidebar";
import { EmptyChatState } from "../components/chat/EmptyChatState";
import { MessageBubble } from "../components/chat/MessageBubble";
import { ApiError, safeError } from "../api/client";
import { streamChat } from "../services/chat";
import { conversations as service } from "../services/conversations";
import type { Conversation, Message } from "../types/chat";
import { documents as documentService } from "../services/documents";
import type { Document } from "../types/document";
import { mcp } from "../services/mcp";
export function ChatWorkspace() {
  const { id } = useParams(),
    nav = useNavigate(),
    location = useLocation(),
    [items, setItems] = useState<Conversation[]>([]),
    [messages, setMessages] = useState<Message[]>([]),
    [loading, setLoading] = useState(true),
    [generating, setGenerating] = useState(false),
    [error, setError] = useState(""),
    [documents, setDocuments] = useState<Document[]>([]),
    [selectedDocuments, setSelectedDocuments] = useState<string[]>([]),
    abort = useRef<AbortController | null>(null),
    bottom = useRef<HTMLDivElement | null>(null),
    sending = useRef(false),
    streamingConversation = useRef<string | null>(null);
  const loadList = useCallback(
    () =>
      service
        .list()
        .then((x) => setItems(x.items))
        .catch(() => setError("Unable to load conversations."))
        .finally(() => setLoading(false)),
    [],
  );
  useEffect(() => {
    loadList();
  }, [loadList]);
  useEffect(() => {
    let active = true;
    const documentId = (location.state as { documentId?: string } | null)?.documentId;
    documentService.all().then((items) => {
      if (!active) return;
      const ready = items.filter((d) => d.status === "ready");
      setDocuments(ready);
      setSelectedDocuments((current) => {
        const valid = current.filter((id) => ready.some((d) => d.id === id));
        return documentId && ready.some((d) => d.id === documentId)
          ? [...new Set([...valid, documentId])].slice(0, 20) : valid;
      });
      if (documentId && !ready.some((d) => d.id === documentId))
        setError("This document is unavailable or is not ready. Choose another source.");
    }).catch((e) => {
      if (active) setError(safeError(e, "Unable to load knowledge. Refresh to try again."));
    });
    return () => { active = false; };
  }, [location.state]);
  useEffect(() => () => { abort.current?.abort(); }, []);
  useEffect(() => {
    if (streamingConversation.current === id) return;
    abort.current?.abort();
    let active = true;
    if (!id) {
      // URL navigation intentionally resets the selected server-backed thread.
      // oxlint-disable-next-line react/set-state-in-effect
      setMessages([]);
      return;
    }
    setError("");
    Promise.all([service.get(id), service.messages(id)])
      .then(([, m]) => { if (active && streamingConversation.current !== id) setMessages(m); })
      .catch((e) => { if (active) setError(safeError(e, "Unable to load this conversation.")); });
    return () => { active = false; };
  }, [id]);
  useEffect(() => {
    // Never return a DOM method's result as React's effect cleanup.
    void bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);
  async function create() {
    try {
      const x = await service.create();
      setItems((v) => [x, ...v]);
      nav(`/app/chat/${x.id}`);
    } catch (e) {
      setError(
        safeError(e, "Unable to create conversation. Check your connection."),
      );
    }
  }
  async function send(text: string) {
    if (sending.current || !text.trim()) return;
    sending.current = true;
    setGenerating(true);
    let cid = id;
    if (!cid) {
      try {
        const x = await service.create();
        cid = x.id;
        setItems((v) => [x, ...v]);
        streamingConversation.current = cid;
        nav(`/app/chat/${cid}`, { replace: true });
      } catch (e) {
        setError(
          safeError(e, "Unable to create conversation. Check your connection."),
        );
        sending.current = false;
        setGenerating(false);
        return;
      }
    }
    streamingConversation.current = cid;
    const now = new Date().toISOString(),
      user: Message = {
        id: crypto.randomUUID(),
        conversation_id: cid,
        role: "user",
        content: text,
        token_count: null,
        created_at: now,
      },
      ai: Message = {
        ...user,
        id: crypto.randomUUID(),
        role: "assistant",
        content: "",
      };
    setMessages((v) => [...v, user, ai]);
    setGenerating(true);
    setError("");
    abort.current = new AbortController();
    try {
      await streamChat(
        cid,
        text,
        selectedDocuments,
        abort.current.signal,
        (e) => {
          if (e.event === "token")
            setMessages((v) =>
              v.map((m) =>
                m.id === ai.id
                  ? { ...m, content: m.content + String(e.data.content) }
                  : m,
              ),
            );
          if (e.event === "sources")
            setMessages((v) =>
              v.map((m) =>
                m.id === ai.id
                  ? { ...m, sources: e.data.items as Message["sources"] }
                  : m,
              ),
            );
          if (e.event === "tool")
            setMessages((v) => v.map((m) => m.id === ai.id
              ? { ...m, tool_calls: [...(m.tool_calls || []), e.data as unknown as NonNullable<Message["tool_calls"]>[number]] }
              : m));
          if (e.event === "error") {
            const code = String(e.data.code || "");
            if (code.startsWith("MCP_")) throw new ApiError(`MCP:${code}`, 502);
            if (code === "LLM_EMPTY_RESPONSE" || code === "LLM_INVALID_RESPONSE")
              throw new ApiError("AI_PROVIDER_INVALID_RESPONSE", 502);
            const status = e.data.code === "LLM_MODEL_UNAVAILABLE" ? 404
              : e.data.code === "LLM_AUTH_FAILED" ? 401
              : e.data.code === "LLM_RATE_LIMITED" ? 429 : 502;
            throw new ApiError("AI_PROVIDER_ERROR", status);
          }
        },
      );
      await loadList();
    } catch (e) {
      if ((e as Error).name === "AbortError") setError("Request cancelled.");
      else if (e instanceof ApiError && e.message === "AI_PROVIDER_ERROR")
        setError(e.status === 404
          ? "The AI provider returned 404. Check that the configured model is available to your Groq account."
          : e.status === 401 ? "The AI provider rejected its credentials or access permissions. Check the backend Groq configuration."
          : e.status === 429 ? "The AI provider rate limit was reached. Please try again later."
          : "The AI provider could not generate a response. Please try again.");
      else if (e instanceof ApiError && e.message === "AI_PROVIDER_INVALID_RESPONSE")
        setError("The AI provider returned an incomplete response. Please retry the request.");
      else if (e instanceof ApiError && e.message.startsWith("MCP:"))
        setError(e.message === "MCP:MCP_INVALID_ARGUMENTS"
          ? "The selected tool received invalid arguments. Try rephrasing the request."
          : e.message === "MCP:MCP_TOOL_DISABLED" || e.message === "MCP:MCP_CONNECTION_DISABLED"
            ? "The selected MCP tool or connection is disabled. Review it in Tools / MCP."
            : "The MCP tool could not complete the request. Review its connection and try again.");
      else setError(safeError(e, "Unable to generate a response. Check your connection and selected documents; the AI or retrieval service may be unavailable."));
      setMessages((v) =>
        v.filter((m) => m.id !== ai.id || m.content.length > 0),
      );
    } finally {
      sending.current = false;
      streamingConversation.current = null;
      setGenerating(false);
    }
  }
  function rename(x: Conversation) {
    const title = prompt("Rename conversation", x.title)?.trim();
    if (title) service.rename(x.id, title).then(loadList).catch((e) => setError(safeError(e, "Unable to rename conversation.")));
  }
  async function resolveApproval(messageId: string, approvalId: string, approve: boolean) {
    try {
      const call = approve ? await mcp.approve(approvalId) : await mcp.deny(approvalId);
      setMessages((current) => current.map((message) => message.id === messageId
        ? { ...message, content: call.final_message_content || message.content,
            tool_calls: message.tool_calls?.map((item) => item.id === call.id ? call : item) }
        : message));
    } catch (e) {
      setError(safeError(e, "Unable to resolve this tool approval."));
    }
  }
  function remove(x: Conversation) {
    if (sending.current) return;
    if (confirm(`Delete “${x.title}”?`))
      service.remove(x.id).then(() => {
        setItems((v) => v.filter((i) => i.id !== x.id));
        if (id === x.id) nav("/app/chat");
      }).catch((e) => setError(safeError(e, "Unable to delete conversation.")));
  }
  return (
    <div className="chat-workspace">
      <ConversationSidebar
        items={items}
        active={id}
        loading={loading}
        onNew={() => { if (!sending.current) void create(); }}
        onOpen={(x) => { if (!sending.current) nav(`/app/chat/${x}`); }}
        onRename={rename}
        onDelete={remove}
      />
      <main className="chat-main">
        <div className="messages">
          {messages.length ? (
            <>
              {messages.map((m, i) => (
                <MessageBubble
                  key={m.id}
                  message={m}
                  generating={generating && i === messages.length - 1}
                  onApproval={(approvalId, approve) => void resolveApproval(m.id, approvalId, approve)}
                />
              ))}
              <div ref={bottom} />
            </>
          ) : (
            <EmptyChatState choose={send} />
          )}
        </div>
        {error && <div className="chat-error">{error}</div>}
        <div className="knowledge-select">
          <select
            aria-label="Attach knowledge"
            disabled={generating || selectedDocuments.length >= 20}
            value=""
            onChange={(e) => {
              const documentId = e.target.value;
              if (documentId && documents.some((d) => d.id === documentId))
                setSelectedDocuments((v) => v.length < 20 && !v.includes(documentId) ? [...v, documentId] : v);
            }}
          >
            <option value="">Attach knowledge…</option>
            {documents
              .filter((d) => !selectedDocuments.includes(d.id))
              .map((d) => (
                <option key={d.id} value={d.id}>
                  {d.display_name}
                </option>
              ))}
          </select>
          {selectedDocuments.map((id) => (
            <button
              key={id}
              disabled={generating}
              aria-label={`Remove ${documents.find((d) => d.id === id)?.display_name}`}
              onClick={() =>
                setSelectedDocuments((v) => v.filter((x) => x !== id))
              }
            >
              {documents.find((d) => d.id === id)?.display_name} ×
            </button>
          ))}
        </div>
        <ChatComposer
          onSend={send}
          generating={generating}
          onStop={() => abort.current?.abort()}
        />
      </main>
    </div>
  );
}

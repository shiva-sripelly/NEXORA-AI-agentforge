import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ChatComposer } from "../components/chat/ChatComposer";
import { ConversationSidebar } from "../components/chat/ConversationSidebar";
import { EmptyChatState } from "../components/chat/EmptyChatState";
import { MessageBubble } from "../components/chat/MessageBubble";
import { streamChat } from "../services/chat";
import { conversations as service } from "../services/conversations";
import type { Conversation, Message } from "../types/chat";
export function ChatWorkspace() {
  const { id } = useParams(),
    nav = useNavigate(),
    [items, setItems] = useState<Conversation[]>([]),
    [messages, setMessages] = useState<Message[]>([]),
    [loading, setLoading] = useState(true),
    [generating, setGenerating] = useState(false),
    [error, setError] = useState(""),
    abort = useRef<AbortController | null>(null),
    bottom = useRef<HTMLDivElement | null>(null);
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
    if (!id) {
      // URL navigation intentionally resets the selected server-backed thread.
      // oxlint-disable-next-line react/set-state-in-effect
      setMessages([]);
      return;
    }
    setError("");
    Promise.all([service.get(id), service.messages(id)])
      .then(([, m]) => setMessages(m))
      .catch(() => setError("Conversation not found."));
  }, [id]);
  useEffect(
    () => bottom.current?.scrollIntoView({ behavior: "smooth" }),
    [messages],
  );
  async function create() {
    try {
      const x = await service.create();
      setItems((v) => [x, ...v]);
      nav(`/app/chat/${x.id}`);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Unable to create conversation.",
      );
    }
  }
  async function send(text: string) {
    let cid = id;
    if (!cid) {
      try {
        const x = await service.create();
        cid = x.id;
        setItems((v) => [x, ...v]);
        nav(`/app/chat/${cid}`, { replace: true });
      } catch (e) {
        setError(
          e instanceof Error ? e.message : "Unable to create conversation.",
        );
        return;
      }
    }
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
      await streamChat(cid, text, abort.current.signal, (e) => {
        if (e.event === "token")
          setMessages((v) =>
            v.map((m) =>
              m.id === ai.id
                ? { ...m, content: m.content + String(e.data.content) }
                : m,
            ),
          );
        if (e.event === "error") throw Error(String(e.data.message));
      });
      await loadList();
    } catch (e) {
      if ((e as Error).name === "AbortError") setError("Request cancelled.");
      else setError(e instanceof Error ? e.message : "Generation failed.");
      setMessages((v) =>
        v.filter((m) => m.id !== ai.id || m.content.length > 0),
      );
    } finally {
      setGenerating(false);
    }
  }
  function rename(x: Conversation) {
    const title = prompt("Rename conversation", x.title)?.trim();
    if (title) service.rename(x.id, title).then(loadList);
  }
  function remove(x: Conversation) {
    if (confirm(`Delete “${x.title}”?`))
      service.remove(x.id).then(() => {
        setItems((v) => v.filter((i) => i.id !== x.id));
        if (id === x.id) nav("/app/chat");
      });
  }
  return (
    <div className="chat-workspace">
      <ConversationSidebar
        items={items}
        active={id}
        loading={loading}
        onNew={create}
        onOpen={(x) => nav(`/app/chat/${x}`)}
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
                />
              ))}
              <div ref={bottom} />
            </>
          ) : (
            <EmptyChatState choose={send} />
          )}
        </div>
        {error && <div className="chat-error">{error}</div>}
        <ChatComposer
          onSend={send}
          generating={generating}
          onStop={() => abort.current?.abort()}
        />
      </main>
    </div>
  );
}

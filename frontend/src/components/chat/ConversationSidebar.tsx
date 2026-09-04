import { MessageSquare, MoreHorizontal, Plus, Trash2 } from "lucide-react";
import type { Conversation } from "../../types/chat";
export function ConversationSidebar({
  items,
  active,
  loading,
  onNew,
  onOpen,
  onRename,
  onDelete,
}: {
  items: Conversation[];
  active?: string;
  loading: boolean;
  onNew: () => void;
  onOpen: (id: string) => void;
  onRename: (x: Conversation) => void;
  onDelete: (x: Conversation) => void;
}) {
  return (
    <aside className="conversation-list">
      <header>
        <strong>Conversations</strong>
        <button onClick={onNew}>
          <Plus />
        </button>
      </header>
      <button className="new-conversation" onClick={onNew}>
        <Plus />
        New chat
      </button>
      <div>
        {loading ? (
          <p>Loading…</p>
        ) : items.length === 0 ? (
          <p>No conversations yet.</p>
        ) : (
          items.map((x) => (
            <article
              key={x.id}
              className={active === x.id ? "selected" : ""}
              onClick={() => onOpen(x.id)}
            >
              <MessageSquare />
              <span>
                <strong>{x.title}</strong>
                <small>{new Date(x.updated_at).toLocaleDateString()}</small>
              </span>
              <button
                title="Rename"
                onClick={(e) => {
                  e.stopPropagation();
                  onRename(x);
                }}
              >
                <MoreHorizontal />
              </button>
              <button
                title="Delete"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(x);
                }}
              >
                <Trash2 />
              </button>
            </article>
          ))
        )}
      </div>
    </aside>
  );
}

import { Bot, Check, Copy } from "lucide-react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message } from "../../types/chat";
export function MessageBubble({
  message,
  generating,
  onApproval,
}: {
  message: Message;
  generating?: boolean;
  onApproval?: (approvalId: string, approve: boolean) => void;
}) {
  const [copied, setCopied] = useState(false),
    assistant = message.role === "assistant";
  function copy() {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  }
  return (
    <article className={assistant ? "bubble assistant" : "bubble user-message"}>
      {assistant && (
        <span className="ai-avatar">
          <Bot />
        </span>
      )}
      <div>
        <header>
          {assistant ? "AgentForge" : "You"}
          {message.content && (
            <button onClick={copy}>{copied ? <Check /> : <Copy />}</button>
          )}
        </header>
        {message.content ? (
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code({ className, children, ...props }) {
                const lang = /language-(\w+)/.exec(className || "")?.[1];
                return className ? (
                  <span className="code-wrap">
                    <em>{lang || "code"}</em>
                    <code className={className} {...props}>
                      {children}
                    </code>
                  </span>
                ) : (
                  <code {...props}>{children}</code>
                );
              },
            }}
          >
            {message.content}
          </ReactMarkdown>
        ) : generating ? (
          <p className="generating">
            <i />
            <i />
            <i /> Generating
          </p>
        ) : null}
        {assistant && message.sources && message.sources.length > 0 && (
          <section className="message-sources">
            <strong>Sources</strong>
            {message.sources.map((s) => (
              <span key={`${s.document_chunk_id}-${s.rank}`}>
                {s.document_name}
                {s.page ? ` — Page ${s.page}` : ""}
              </span>
            ))}
          </section>
        )}
        {assistant && message.tool_calls?.map((call) => (
          <section className="tool-activity" key={call.id}>
            <strong>{call.status === "awaiting_approval" ? "Tool approval required" : "Tool activity"}</strong>
            <span>{call.tool_name}</span>
            <small>Status: {call.status.replace("_", " ")}</small>
            {call.result_summary && <small>Result: {call.result_summary}</small>}
            {call.status === "awaiting_approval" && call.approval_id && onApproval && <div>
              <button onClick={() => onApproval(call.approval_id!, true)}>Approve</button>
              <button onClick={() => onApproval(call.approval_id!, false)}>Deny</button>
            </div>}
          </section>
        ))}
      </div>
    </article>
  );
}

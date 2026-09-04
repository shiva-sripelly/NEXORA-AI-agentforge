import { Bot, Check, Copy } from "lucide-react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message } from "../../types/chat";
export function MessageBubble({
  message,
  generating,
}: {
  message: Message;
  generating?: boolean;
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
      </div>
    </article>
  );
}

import { ArrowUp, Square } from "lucide-react";
import { type KeyboardEvent, useState } from "react";
export function ChatComposer({
  onSend,
  generating,
  onStop,
  initial = "",
}: {
  onSend: (v: string) => void;
  generating: boolean;
  onStop: () => void;
  initial?: string;
}) {
  const [value, setValue] = useState(initial);
  function send() {
    const v = value.trim();
    if (v && !generating) {
      setValue("");
      onSend(v);
    }
  }
  function key(e: KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }
  return (
    <div className="composer">
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={key}
        maxLength={10000}
        placeholder="Ask AgentForge anything…"
        rows={1}
      />
      {generating ? (
        <button onClick={onStop} className="stop">
          <Square />
          Stop
        </button>
      ) : (
        <button onClick={send} disabled={!value.trim()}>
          <ArrowUp />
        </button>
      )}
      <small>AgentForge can make mistakes. Verify important information.</small>
    </div>
  );
}

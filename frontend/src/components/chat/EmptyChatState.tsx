import { Sparkles } from "lucide-react";
const prompts = [
  "Explain a backend architecture",
  "Help debug a Python function",
  "Design a PostgreSQL schema",
  "Explain an algorithm",
];
export function EmptyChatState({ choose }: { choose: (v: string) => void }) {
  return (
    <div className="chat-empty">
      <span>
        <Sparkles />
      </span>
      <h1>What can I help you build?</h1>
      <p>Ask a technical question or start exploring an idea.</p>
      <section>
        {prompts.map((x) => (
          <button key={x} onClick={() => choose(x)}>
            {x}
          </button>
        ))}
      </section>
    </div>
  );
}

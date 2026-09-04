import {
  ArrowUpRight,
  BookOpen,
  CircleCheck,
  Clock3,
  MessageSquare,
  PlugZap,
  Plus,
  Sparkles,
  Workflow,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
const cards = [
  ["Conversations", "Ready to start", MessageSquare],
  ["Agent runs", "No runs yet", Workflow],
  ["Connected tools", "Configure MCP", PlugZap],
  ["Knowledge docs", "Add your first source", BookOpen],
] as const;
export function Dashboard() {
  const { user } = useAuth();
  return (
    <div className="dashboard">
      <section className="welcome">
        <div>
          <small>
            <Sparkles /> YOUR AI CONTROL PLANE
          </small>
          <h1>Welcome back, {user?.name.split(" ")[0]}.</h1>
          <p>
            Your workspace is ready. Connect knowledge and tools to start
            forging intelligent agents.
          </p>
        </div>
        <button disabled>
          <Plus />
          Create agent
        </button>
      </section>
      <section className="stats">
        {cards.map(([name, hint, Icon]) => (
          <article key={name}>
            <Icon />
            <div>
              <small>{name}</small>
              <strong>0</strong>
              <p>{hint}</p>
            </div>
            <ArrowUpRight />
          </article>
        ))}
      </section>
      <div className="grid">
        <section className="panel">
          <h3>Start building</h3>
          <p>Set up the building blocks of your first agent workflow.</p>
          {[
            [
              "01",
              "Add knowledge",
              "Upload documents to ground agents in trusted context.",
            ],
            [
              "02",
              "Connect MCP tools",
              "Give agents access to real-world capabilities.",
            ],
            [
              "03",
              "Forge your first agent",
              "Combine a model, knowledge and tools.",
            ],
          ].map((x) => (
            <article className="step" key={x[0]}>
              <b>{x[0]}</b>
              <div>
                <strong>{x[1]}</strong>
                <p>{x[2]}</p>
              </div>
            </article>
          ))}
        </section>
        <section className="panel activity">
          <h3>Recent activity</h3>
          <p>Latest events in your workspace.</p>
          <div>
            <Clock3 />
            <strong>No activity yet</strong>
            <small>
              Your conversations, runs and tool calls will appear here.
            </small>
          </div>
        </section>
      </div>
      <section className="status">
        <div>
          <CircleCheck />
          <span>
            <strong>Workspace is ready</strong>
            <small>Authentication and core services are operational.</small>
          </span>
        </div>
        <p>
          <i />
          API　 <i />
          Database　 <i />
          Authentication
        </p>
      </section>
    </div>
  );
}

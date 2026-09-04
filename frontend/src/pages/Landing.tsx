import {
  ArrowRight,
  Bot,
  BrainCircuit,
  DatabaseZap,
  ShieldCheck,
  Sparkles,
  TerminalSquare,
} from "lucide-react";
import { Link } from "react-router-dom";
import { Brand } from "../components/Brand";
export function Landing() {
  return (
    <div className="landing">
      <nav>
        <Brand />
        <div>
          <a href="#features">Platform</a>
          <a href="#architecture">Architecture</a>
          <Link to="/login">Sign in</Link>
          <Link className="cta" to="/register">
            Start building <ArrowRight />
          </Link>
        </div>
      </nav>
      <main>
        <span>
          <Sparkles /> The agentic workspace for modern builders
        </span>
        <h1>
          Build agents that
          <br />
          <i>reason, connect, and act.</i>
        </h1>
        <p>
          Build, connect and run intelligent AI agents powered by LLMs, RAG, MCP
          tools and real-world data.
        </p>
        <div>
          <Link to="/register">
            Start building <ArrowRight />
          </Link>
          <a href="#architecture">View architecture</a>
        </div>
        <section>
          <b>
            <Bot />
            Agent Engine <small>Plan & orchestrate</small>
          </b>
          <article>
            <b>
              <BrainCircuit />
              LLM
            </b>
            <b>
              <DatabaseZap />
              RAG
            </b>
            <b>
              <TerminalSquare />
              MCP
            </b>
          </article>
        </section>
      </main>
      <div id="features" className="features">
        {[
          [BrainCircuit, "Agent workflows"],
          [TerminalSquare, "MCP ecosystem"],
          [DatabaseZap, "Grounded knowledge"],
          [ShieldCheck, "Human approval"],
        ].map(([Icon, title]) => (
          <div key={title as string}>
            <Icon />
            <h3>{title as string}</h3>
            <p>Secure, traceable and built for production.</p>
          </div>
        ))}
      </div>
      <section id="architecture" className="architecture">
        <small>PRODUCTION ARCHITECTURE</small>
        <h2>One workspace. Every layer connected.</h2>
        <p>
          React Frontend　→　FastAPI　→　Agent Engine　→　LLM + RAG +
          MCP　→　PostgreSQL + pgvector
        </p>
      </section>
    </div>
  );
}

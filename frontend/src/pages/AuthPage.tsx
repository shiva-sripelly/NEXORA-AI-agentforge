import {
  ArrowRight,
  Check,
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
  UserRound,
} from "lucide-react";
import { type FormEvent, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { Brand } from "../components/Brand";
import { useAuth } from "../context/AuthContext";
export function AuthPage({ mode }: { mode: "login" | "register" }) {
  const { user, login, register } = useAuth(),
    nav = useNavigate(),
    [show, setShow] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    signup = mode === "register";
  if (user) return <Navigate to="/app" />;
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const d = new FormData(e.currentTarget);
    try {
      if (signup) {
        await register(
          String(d.get("name")),
          String(d.get("email")),
          String(d.get("password")),
        );
      } else {
        await login(String(d.get("email")), String(d.get("password")));
      }
      nav("/app");
    } catch (x) {
      setError(x instanceof Error ? x.message : "Unable to continue");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="auth">
      <header>
        <Link to="/">
          <Brand />
        </Link>
        <span>Secure agent workspace</span>
      </header>
      <main>
        <section className="pitch">
          <p className="eyebrow">● MCP-POWERED INTELLIGENCE</p>
          <h1>
            {signup
              ? "Build agents that work with you."
              : "Welcome back to the forge."}
          </h1>
          <p>
            Connect models, knowledge and real-world tools in one secure
            workspace built for reliable agent execution.
          </p>
          <ul>
            {[
              "Ground answers in your knowledge",
              "Connect tools through MCP",
              "Keep humans in control",
            ].map((x) => (
              <li key={x}>
                <Check />
                {x}
              </li>
            ))}
          </ul>
          <blockquote>
            “The control plane for our AI workflows.”
            <small>Built for developers and modern teams</small>
          </blockquote>
        </section>
        <section className="auth-card">
          <small>{signup ? "CREATE YOUR WORKSPACE" : "WELCOME BACK"}</small>
          <h2>
            {signup
              ? "Start building with AgentForge"
              : "Sign in to AgentForge"}
          </h2>
          <p>
            {signup
              ? "Set up your secure workspace in seconds."
              : "Enter your details to continue."}
          </p>
          <form onSubmit={submit}>
            {signup && (
              <label>
                Full name
                <div>
                  <UserRound />
                  <input
                    name="name"
                    minLength={2}
                    required
                    placeholder="Alex Morgan"
                  />
                </div>
              </label>
            )}
            <label>
              Email address
              <div>
                <Mail />
                <input
                  name="email"
                  type="email"
                  required
                  placeholder="you@company.com"
                />
              </div>
            </label>
            <label>
              Password
              <div>
                <LockKeyhole />
                <input
                  name="password"
                  type={show ? "text" : "password"}
                  minLength={8}
                  required
                  placeholder="••••••••"
                />
                <button type="button" onClick={() => setShow(!show)}>
                  {show ? <EyeOff /> : <Eye />}
                </button>
              </div>
            </label>
            {signup && (
              <p className="hint">
                Use 8+ characters with uppercase, lowercase and a number.
              </p>
            )}
            {error && <div className="error">{error}</div>}
            <button className="submit" disabled={busy}>
              {busy ? "Please wait…" : signup ? "Create workspace" : "Sign in"}
              <ArrowRight />
            </button>
          </form>
          <p className="switch">
            {signup ? "Already have an account?" : "New to AgentForge?"}{" "}
            <Link to={signup ? "/login" : "/register"}>
              {signup ? "Sign in" : "Create an account"}
            </Link>
          </p>
        </section>
      </main>
    </div>
  );
}

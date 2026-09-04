import {
  Bell,
  Bot,
  BookOpen,
  ChartNoAxesCombined,
  Command,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquarePlus,
  PlugZap,
  Search,
  Settings,
  Workflow,
  X,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { Brand } from "../components/Brand";
import { useAuth } from "../context/AuthContext";
const links = [
  ["/app", "Overview", LayoutDashboard],
  ["/app/chat", "Workspace", Command],
  ["/app/agents", "Agents", Bot],
  ["/app/knowledge", "Knowledge Base", BookOpen],
  ["/app/mcp", "MCP Tools", PlugZap],
  ["/app/runs", "Agent Runs", Workflow],
  ["/app/analytics", "Analytics", ChartNoAxesCombined],
  ["/app/settings", "Settings", Settings],
] as const;
export function AppLayout() {
  const [open, setOpen] = useState(false),
    { user, logout } = useAuth();
  return (
    <div className="shell">
      {open && <button className="backdrop" onClick={() => setOpen(false)} />}
      <aside className={open ? "open" : ""}>
        <div className="aside-head">
          <Brand />
          <button onClick={() => setOpen(false)}>
            <X />
          </button>
        </div>
        <button className="new" disabled title="Available in Phase 2">
          <MessageSquarePlus />
          New chat <small>⌘ K</small>
        </button>
        <label>WORKSPACE</label>
        <nav>
          {links.map(([to, name, Icon], i) => (
            <NavLink
              end={i === 0}
              to={to}
              key={to}
              onClick={() => setOpen(false)}
            >
              <Icon />
              {name}
              {name === "MCP Tools" && <em />}
            </NavLink>
          ))}
        </nav>
        <div className="user">
          <span>{user?.name.slice(0, 2).toUpperCase()}</span>
          <div>
            <strong>{user?.name}</strong>
            <small>
              {user?.role === "ADMIN" ? "Administrator" : "Pro workspace"}
            </small>
          </div>
          <button onClick={logout}>
            <LogOut />
          </button>
        </div>
      </aside>
      <main>
        <header>
          <div>
            <button className="menu" onClick={() => setOpen(true)}>
              <Menu />
            </button>
            <section>
              <small>AgentForge / Workspace</small>
              <strong>Workspace overview</strong>
            </section>
          </div>
          <div className="tools">
            <label>
              <Search />
              <input placeholder="Search workspace…" />
            </label>
            <span className="health">
              <i />
              All systems operational
            </span>
            <button>
              <Bell />
            </button>
          </div>
        </header>
        <Outlet />
      </main>
    </div>
  );
}

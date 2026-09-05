import { Cable, Play, RefreshCw, ShieldCheck, Trash2, Wrench } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { safeError } from "../api/client";
import { mcp } from "../services/mcp";
import type { Approval, MCPConnection, MCPTool, ToolCall } from "../types/mcp";

function defaults(tool: MCPTool) {
  if (tool.external_name === "calculate_statistics") return { numbers: [10, 20, 30, 40, 50] };
  if (tool.external_name === "analyze_text") return { text: "AgentForge MCP" };
  return { path: tool.external_name === "list_files" ? "." : "agentforge-note.txt" };
}

export function MCPPage() {
  const [connections, setConnections] = useState<MCPConnection[]>([]),
    [tools, setTools] = useState<MCPTool[]>([]), [calls, setCalls] = useState<ToolCall[]>([]),
    [approvals, setApprovals] = useState<Approval[]>([]), [busy, setBusy] = useState(""),
    [error, setError] = useState("");
  const load = useCallback(async () => {
    const [c, t, h, a] = await Promise.all([mcp.connections(), mcp.tools(), mcp.calls(), mcp.approvals()]);
    setConnections(c); setTools(t); setCalls(h); setApprovals(a);
  }, []);
  useEffect(() => {
    let active = true;
    void load().catch((e) => { if (active) setError(safeError(e, "Unable to load MCP tools.")); });
    return () => { active = false; };
  }, [load]);
  async function action(key: string, work: () => Promise<unknown>) {
    if (busy) return;
    setBusy(key); setError("");
    try { await work(); await load(); }
    catch (e) { setError(safeError(e, "The MCP operation failed. Check the server and try again.")); }
    finally { setBusy(""); }
  }
  function run(tool: MCPTool) {
    const raw = prompt(`Arguments for ${tool.external_name} (JSON)`, JSON.stringify(defaults(tool), null, 2));
    if (raw === null) return;
    let args: Record<string, unknown>;
    try { args = JSON.parse(raw) as Record<string, unknown>; }
    catch { setError("Enter a valid JSON object for tool arguments."); return; }
    void action(`run-${tool.id}`, () => mcp.execute(tool.id, args));
  }
  return <div className="mcp-page">
    <header><div><small>MCP WORKSPACE</small><h1>Tools / MCP</h1><p>Connect approved local servers, discover their capabilities, and review every execution.</p></div>
      <div><button disabled={!!busy || connections.some((c) => c.server_type === "analytics")} onClick={() => action("add-analytics", () => mcp.add("analytics"))}>+ Analytics</button>
      <button disabled={!!busy || connections.some((c) => c.server_type === "file")} onClick={() => action("add-file", () => mcp.add("file"))}>+ Files</button></div></header>
    {error && <p className="mcp-error">{error}</p>}
    <section className="mcp-panel"><h2><Cable /> Connections</h2>
      {!connections.length ? <p className="mcp-empty">Add a safe local MCP server to begin.</p> : connections.map((item) => <article key={item.id}>
        <div><strong>{item.name}</strong><small>{item.server_type} · {item.transport} · {item.is_enabled ? "enabled" : "disabled"}</small></div><span className={`mcp-state ${item.status}`}>{item.status}</span>
        <button disabled={!!busy} onClick={() => action(`connect-${item.id}`, () => mcp.connect(item.id))}>Connect</button>
        <button disabled={!!busy} onClick={() => action(`refresh-${item.id}`, () => mcp.refresh(item.id))}><RefreshCw /> Refresh tools</button>
        <button aria-label={`Delete ${item.name}`} disabled={!!busy} onClick={() => confirm(`Delete ${item.name}?`) && action(`delete-${item.id}`, () => mcp.removeConnection(item.id))}><Trash2 /></button>
      </article>)}</section>
    <section className="mcp-panel"><h2><Wrench /> Available Tools</h2>
      {!tools.length ? <p className="mcp-empty">Connect a server to discover tools.</p> : tools.map((tool) => <article key={tool.id}>
        <div><strong>{tool.display_name}</strong><small>{tool.description}<br />{tool.connection_name} · <b className={`risk ${tool.risk_level}`}>{tool.risk_level} risk</b></small></div>
        <label><input type="checkbox" checked={tool.is_enabled} disabled={!!busy} onChange={(e) => action(`toggle-${tool.id}`, () => mcp.updateTool(tool.id, { is_enabled: e.target.checked }))} /> Enabled</label>
        <label><input type="checkbox" checked={tool.requires_approval} disabled={!!busy} onChange={(e) => action(`approval-${tool.id}`, () => mcp.updateTool(tool.id, { requires_approval: e.target.checked }))} /> Approval</label>
        <button disabled={!!busy || !tool.is_enabled} onClick={() => run(tool)}><Play /> Run</button>
      </article>)}</section>
    {!!approvals.length && <section className="mcp-panel approvals"><h2><ShieldCheck /> Pending Approvals</h2>{approvals.map((approval) => <article key={approval.id}>
      <div><strong>{approval.tool_name}</strong><small>{approval.risk_level} risk · {JSON.stringify(approval.arguments_summary)}</small></div>
      <button disabled={!!busy} onClick={() => action(`approve-${approval.id}`, () => mcp.approve(approval.id))}>Approve</button>
      <button className="danger" disabled={!!busy} onClick={() => action(`deny-${approval.id}`, () => mcp.deny(approval.id))}>Deny</button>
    </article>)}</section>}
    <section className="mcp-panel"><h2>Tool Call History</h2>{!calls.length ? <p className="mcp-empty">No tool calls yet.</p> : calls.map((call) => <article key={call.id}>
      <div><strong>{call.tool_name}</strong><small>{call.result_summary || call.error_message || JSON.stringify(call.arguments_summary)}{call.conversation_id ? ` · conversation ${call.conversation_id.slice(0, 8)}` : ""}</small></div>
      <span className={`mcp-state ${call.status}`}>{call.status.replace("_", " ")}</span><time>{new Date(call.created_at || "").toLocaleString()}</time>
    </article>)}</section>
  </div>;
}

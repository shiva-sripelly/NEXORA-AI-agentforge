import { ScrollText, ShieldCheck, SlidersHorizontal, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { safeError } from "../api/client";
import { governance } from "../services/governance";
import type { AuditEvent, GovernanceTool, ToolPolicy } from "../types/governance";

export function GovernancePage() {
  const [tools, setTools] = useState<GovernanceTool[]>([]), [policies, setPolicies] = useState<ToolPolicy[]>([]),
    [audit, setAudit] = useState<AuditEvent[]>([]), [busy, setBusy] = useState(""), [error, setError] = useState("");
  const load = useCallback(async () => { const [t, p, a] = await Promise.all([
    governance.tools(), governance.policies(), governance.audit()]); setTools(t); setPolicies(p); setAudit(a); }, []);
  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect -- initial server synchronization
    void load().catch((e) => setError(safeError(e, "Unable to load governance settings.")));
  }, [load]);
  async function action(key: string, work: () => Promise<unknown>) {
    if (busy) return; setBusy(key); setError("");
    try { await work(); await load(); } catch (e) { setError(safeError(e, "The governance change could not be saved.")); }
    finally { setBusy(""); }
  }
  function addPolicy() {
    if (!tools.length) return;
    const toolId = prompt("Tool ID", tools[0].id)?.trim(); if (!toolId) return;
    const subjectInput = prompt("Subject: global, USER, ADMIN, or user:<UUID>", "USER")?.trim(); if (!subjectInput) return;
    const subject = subjectInput.toUpperCase();
    const effect = prompt("Effect: allow or deny", "allow")?.trim().toLowerCase();
    if (effect !== "allow" && effect !== "deny") { setError("Policy effect must be allow or deny."); return; }
    const mode = prompt("Approval mode: never, always, or risk_based", "risk_based")?.trim().toLowerCase();
    if (!mode || !["never", "always", "risk_based"].includes(mode)) { setError("Choose a valid approval mode."); return; }
    const role = subject === "USER" || subject === "ADMIN" ? subject : undefined;
    const userId = subjectInput.toLowerCase().startsWith("user:") ? subjectInput.slice(5).trim() : undefined;
    if (!role && subject !== "GLOBAL" && !userId) { setError("Use global, USER, ADMIN, or user:<UUID>."); return; }
    void action("new-policy", () => governance.createPolicy({ tool_id: toolId, role, user_id: userId, effect,
      approval_mode: mode as "never" | "always" | "risk_based" }));
  }
  return <div className="governance-page">
    <header><small>ADMINISTRATION</small><h1>Tool Governance</h1><p>Configure registry risk, approval defaults, and explicit permission policies.</p></header>
    {error && <p className="mcp-error">{error}</p>}
    <section className="governance-panel"><h2><SlidersHorizontal /> Tool controls</h2>{tools.map((tool) => <article key={tool.id}>
      <div><strong>{tool.display_name}</strong><small>{tool.connection_name} · {tool.external_name}</small></div>
      <label>Risk<select value={tool.risk_level} disabled={!!busy} onChange={(e) => action(`risk-${tool.id}`, () => governance.updateTool(tool.id,
        { risk_level: e.target.value as GovernanceTool["risk_level"] }))}>{["low", "medium", "high", "critical"].map((x) => <option key={x}>{x}</option>)}</select></label>
      <label>Approval<select value={tool.approval_mode} disabled={!!busy} onChange={(e) => action(`mode-${tool.id}`, () => governance.updateTool(tool.id,
        { approval_mode: e.target.value as GovernanceTool["approval_mode"] }))}>{["never", "always", "risk_based"].map((x) => <option key={x}>{x}</option>)}</select></label>
      <label><input type="checkbox" checked={tool.is_enabled} disabled={!!busy} onChange={(e) => action(`enabled-${tool.id}`, () => governance.updateTool(tool.id,
        { is_enabled: e.target.checked }))} /> Enabled</label>
    </article>)}</section>
    <section className="governance-panel"><h2><ShieldCheck /> Policies <button disabled={!!busy} onClick={addPolicy}>+ Policy</button></h2>
      {!policies.length ? <p className="mcp-empty">No explicit policies. Tool defaults apply.</p> : policies.map((item) => <article key={item.id}>
        <div><strong>{item.tool_name}</strong><small>{item.user_id ? `user ${item.user_id.slice(0, 8)}` : item.role || "global"} · {item.effect} · {item.approval_mode || "tool default"}</small></div>
        <button aria-label="Delete policy" disabled={!!busy} onClick={() => action(`delete-${item.id}`, () => governance.removePolicy(item.id))}><Trash2 /></button>
      </article>)}</section>
    <section className="governance-panel audit-list"><h2><ScrollText /> Audit events</h2>{audit.slice(0, 100).map((item) => <article key={item.id}>
      <div><strong>{item.event_type.replaceAll("_", " ")}</strong><small>{new Date(item.created_at).toLocaleString()} · {JSON.stringify(item.metadata)}</small></div>
    </article>)}</section>
  </div>;
}

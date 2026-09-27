import { Check, Clock3, ShieldCheck, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { safeError } from "../api/client";
import { mcp } from "../services/mcp";
import type { Approval } from "../types/mcp";

export function ApprovalsPage() {
  const [items, setItems] = useState<Approval[]>([]), [busy, setBusy] = useState(""), [error, setError] = useState("");
  const load = useCallback(() => mcp.approvals(false).then(setItems), []);
  useEffect(() => { void load().catch((e) => setError(safeError(e, "Unable to load approvals."))); }, [load]);
  async function resolve(item: Approval, approve: boolean) {
    const note = prompt(`${approve ? "Approve" : "Deny"} ${item.tool_name}. Optional resolution note:`) ?? undefined;
    if (note === undefined) return;
    setBusy(item.id); setError("");
    try { if (approve) await mcp.approve(item.id, note); else await mcp.deny(item.id, note); await load(); }
    catch (e) { setError(safeError(e, "This approval could not be resolved. It may be stale or expired.")); }
    finally { setBusy(""); }
  }
  const pending = items.filter((item) => item.status === "pending"), resolved = items.filter((item) => item.status !== "pending");
  return <div className="governance-page approvals-page">
    <header><small>HUMAN-IN-THE-LOOP</small><h1>Approvals</h1><p>Review governed tool actions before execution.</p></header>
    {error && <p className="mcp-error">{error}</p>}
    <ApprovalList title="Pending" items={pending} busy={busy} onResolve={resolve} />
    <ApprovalList title="Resolved" items={resolved} busy={busy} onResolve={resolve} />
  </div>;
}

function ApprovalList({ title, items, busy, onResolve }: { title: string; items: Approval[]; busy: string;
    onResolve: (item: Approval, approve: boolean) => void }) {
  return <section className="governance-panel"><h2>{title === "Pending" ? <Clock3 /> : <ShieldCheck />}{title}</h2>
    {!items.length ? <p className="mcp-empty">No {title.toLowerCase()} approvals.</p> : items.map((item) => <article key={item.id}>
      <div className="approval-summary"><strong>{item.tool_name}</strong>
        <span><b className={`risk ${item.risk_level}`}>{item.risk_level}</b><b className={`approval-status ${item.status}`}>{item.status}</b></span>
        {item.reason && <small><b>Reason:</b> {item.reason}</small>}
        <small><b>Arguments:</b> <code>{JSON.stringify(item.arguments_summary)}</code></small>
        {item.agent_goal && <small><b>Agent goal:</b> {item.agent_goal}</small>}
        {item.conversation_id && <small><b>Conversation:</b> {item.conversation_id.slice(0, 8)}</small>}
        <small>Requested {new Date(item.requested_at).toLocaleString()}</small>
        {item.resolution_note && <small><b>Resolution:</b> {item.resolution_note}</small>}
        {item.resolved_by_user_id && <small>Resolved by {item.resolved_by_name || item.resolved_by_user_id.slice(0, 8)}</small>}
      </div>
      {item.status === "pending" && <div className="approval-actions">
        <button disabled={!!busy} onClick={() => onResolve(item, true)}><Check /> Approve</button>
        <button className="danger" disabled={!!busy} onClick={() => onResolve(item, false)}><X /> Deny</button>
      </div>}
    </article>)}</section>;
}

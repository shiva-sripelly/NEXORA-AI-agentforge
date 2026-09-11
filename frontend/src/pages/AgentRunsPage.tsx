import { useEffect, useState } from "react";
import { AgentRunCard } from "../components/agents/AgentRunCard";
import { safeError } from "../api/client";
import { agents } from "../services/agents";
import { mcp } from "../services/mcp";
import type { AgentRun } from "../types/agent";

export function AgentRunsPage() {
  const [runs, setRuns] = useState<AgentRun[]>([]), [selected, setSelected] = useState<AgentRun | null>(null),
    [error, setError] = useState(""), [busy, setBusy] = useState(false);
  async function load(selectId?: string) {
    const items = await agents.list(); setRuns(items);
    setSelected(items.find((item) => item.id === selectId) || items[0] || null);
  }
  useEffect(() => {
    let active = true;
    void agents.list().then((items) => { if (active) { setRuns(items); setSelected(items[0] || null); } })
      .catch((e) => { if (active) setError(safeError(e, "Unable to load agent runs.")); });
    return () => { active = false; };
  }, []);
  async function approval(id: string, approve: boolean) {
    if (busy || !selected) return; setBusy(true); setError("");
    try { if (approve) await mcp.approve(id); else await mcp.deny(id); await load(selected.id); }
    catch (e) { setError(safeError(e, "Unable to resolve approval.")); }
    finally { setBusy(false); }
  }
  async function cancel() {
    if (busy || !selected) return; setBusy(true);
    try { await agents.cancel(selected.id); await load(selected.id); }
    catch (e) { setError(safeError(e, "Unable to cancel agent run.")); }
    finally { setBusy(false); }
  }
  return <div className="agent-history-page">
    <header><small>CONTROLLED EXECUTION</small><h1>Agent Runs</h1><p>Review persisted plans, tool activity, approvals, and outcomes.</p></header>
    {error && <div className="agent-run-error">{error}</div>}
    <div className="agent-history-grid"><aside>{runs.length ? runs.map((run) => <button className={selected?.id === run.id ? "active" : ""} key={run.id} onClick={() => setSelected(run)}>
      <strong>{run.goal}</strong><small>{run.status.replaceAll("_", " ")} · {new Date(run.created_at).toLocaleString()}</small>
    </button>) : <p>No agent runs yet.</p>}</aside>
      <main>{selected ? <AgentRunCard run={selected} onApprove={(id) => void approval(id, true)} onDeny={(id) => void approval(id, false)} onCancel={() => void cancel()} />
        : <p>Select a run to inspect its execution steps.</p>}</main></div>
  </div>;
}

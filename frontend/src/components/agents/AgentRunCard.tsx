import { Ban, Check, Circle, Clock3, ShieldAlert, X } from "lucide-react";
import type { AgentRun } from "../../types/agent";

export function AgentRunCard({ run, onApprove, onDeny, onCancel }: {
  run: AgentRun;
  onApprove?: (approvalId: string) => void;
  onDeny?: (approvalId: string) => void;
  onCancel?: () => void;
}) {
  const stoppable = ["planning", "running", "awaiting_approval"].includes(run.status);
  return <section className="agent-run-card">
    <header><div><small>AGENT RUN</small><strong>{run.goal}</strong></div>
      <span className={`agent-run-status ${run.status}`}>{run.status.replaceAll("_", " ")}</span></header>
    <div className="agent-progress"><span style={{ width: `${run.total_steps ? (run.steps.filter((s) => s.status === "completed").length / run.total_steps) * 100 : 8}%` }} /></div>
    <p>Step {Math.min(run.current_step, run.total_steps)} of {run.total_steps || "…"}</p>
    <div className="agent-step-list">{run.steps.map((step) => <article key={step.id} className={step.status}>
      {step.status === "completed" ? <Check /> : step.status === "failed" ? <X />
        : step.status === "awaiting_approval" ? <ShieldAlert /> : step.status === "cancelled" ? <Ban />
          : step.status === "running" ? <Clock3 /> : <Circle />}
      <div><strong>Step {step.step_number} — {step.title}</strong>
        <small>{step.tool_name || step.step_type} · {step.status.replaceAll("_", " ")}</small>
        {step.result_summary && <small>{step.result_summary}</small>}
        {step.error_message && <small className="agent-step-error">{step.error_message}</small>}
        {step.status === "awaiting_approval" && step.approval_id && <div className="agent-approval">
          <button onClick={() => onApprove?.(step.approval_id!)}>Approve</button>
          <button onClick={() => onDeny?.(step.approval_id!)}>Deny</button>
        </div>}
      </div>
    </article>)}</div>
    {run.error_message && <div className="agent-run-error">{run.error_message}</div>}
    {stoppable && onCancel && <button className="agent-cancel" onClick={onCancel}>Cancel run</button>}
  </section>;
}

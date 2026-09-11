import json
import logging

from jsonschema import ValidationError, validate

from app.ai.agents.references import validate_references
from app.schemas.agent import ExecutionPlan

log = logging.getLogger(__name__)


class AgentPlanError(ValueError):
    pass


class AgentPlanner:
    async def create_plan(self, provider, model: str, goal: str, tools: list[dict], documents: list[dict],
            max_steps: int, require_tool: bool = False, correction: str | None = None) -> ExecutionPlan:
        system = """Create only a safe JSON execution plan. Do not provide prose, chain-of-thought, or private reasoning.
Return exactly {"goal": string, "steps": [{"step_number": integer, "type": "tool"|"rag"|"final", "title": string, "description": string|null, "tool_name": string|null, "arguments": object}]}.
Use only tool names supplied below. Add a rag step only when documents are supplied and the goal needs them. End with exactly one final step.
For a later tool argument that consumes an earlier result, use {"$from_step": N, "path": "field"}. To convert text file content into numbers use {"$from_step": N, "path": "content", "transform": "number_list"}.
Never invent a tool, result, file, document, or extra step. Keep the plan minimal.
When required_tool_use is true, the plan MUST contain at least one appropriate tool step followed by a final step. Never replace required tool execution with model calculation or a final-only answer."""
        payload = {"goal": goal, "maximum_steps": max_steps, "required_tool_use": require_tool,
            "available_tools": tools, "selected_documents": documents}
        if correction: payload["correction"] = correction
        raw = await provider.complete_json([{"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload)}], model)
        try:
            return ExecutionPlan.model_validate(_normalize_plan(raw, goal))
        except Exception as exc:
            log.warning("agent_plan_parse_failed validation_error=%s", type(exc).__name__)
            raise AgentPlanError("The planner returned an invalid execution plan") from exc


def _normalize_plan(raw: dict, goal: str) -> dict:
    """Normalize harmless provider formatting while keeping the plan schema strict."""
    value = raw.get("plan") if isinstance(raw.get("plan"), dict) else raw
    steps = value.get("steps") if isinstance(value, dict) else None
    if not isinstance(steps, list):
        return value
    normalized = []
    for position, item in enumerate(steps, start=1):
        if not isinstance(item, dict):
            normalized.append(item)
            continue
        step_type = item.get("type", item.get("step_type", item.get("kind")))
        tool_name = item.get("tool_name", item.get("tool"))
        if isinstance(tool_name, dict):
            tool_name = tool_name.get("name")
        if step_type == "function" and tool_name:
            step_type = "tool"
        arguments = item.get("arguments", item.get("input", {}))
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                pass
        if step_type != "tool":
            tool_name, arguments = None, {}
        normalized.append({
            "step_number": item.get("step_number", item.get("number", position)),
            "type": step_type,
            "title": item.get("title") or item.get("name") or f"Step {position}",
            "description": item.get("description"),
            "tool_name": tool_name,
            "arguments": arguments,
        })
    return {"goal": value.get("goal") or goal, "steps": normalized}


class PlanValidator:
    def validate(self, plan: ExecutionPlan, tools_by_name: dict, has_documents: bool, max_steps: int,
            max_tool_calls: int, require_tool: bool = False) -> None:
        if len(plan.steps) > max_steps:
            raise AgentPlanError("Plan exceeds the maximum step limit")
        numbers = [step.step_number for step in plan.steps]
        if numbers != list(range(1, len(plan.steps) + 1)):
            raise AgentPlanError("Plan step numbers must be consecutive and unique")
        finals = [step for step in plan.steps if step.step_type == "final"]
        if len(finals) != 1 or plan.steps[-1].step_type != "final":
            raise AgentPlanError("Plan must end with exactly one final step")
        tool_steps = [step for step in plan.steps if step.step_type == "tool"]
        if require_tool and not tool_steps:
            raise AgentPlanError("The requested MCP tool is not enabled, connected, or selected by the planner.")
        if len(tool_steps) > max_tool_calls:
            raise AgentPlanError("Plan exceeds the maximum tool-call limit")
        if any(step.step_type == "rag" for step in plan.steps) and not has_documents:
            raise AgentPlanError("Plan requested retrieval without selected documents")
        for step in tool_steps:
            tool = tools_by_name.get(step.tool_name)
            if not tool:
                raise AgentPlanError("Plan selected an unavailable tool")
            validate_references(step.arguments, step.step_number)
            if not list(_reference_values(step.arguments)):
                try:
                    validate(instance=step.arguments, schema=tool.input_schema)
                except ValidationError as exc:
                    raise AgentPlanError("Plan contains invalid tool arguments") from exc


def _reference_values(value):
    if isinstance(value, dict):
        if "$from_step" in value:
            yield value
        else:
            for child in value.values(): yield from _reference_values(child)
    elif isinstance(value, list):
        for child in value: yield from _reference_values(child)

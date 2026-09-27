import json
import logging
import re

from jsonschema import ValidationError, validate

from app.ai.agents.references import validate_references
from app.schemas.agent import ExecutionPlan

log = logging.getLogger(__name__)


class AgentPlanError(ValueError):
    pass


_NAMED_FILE = re.compile(r"(?<![\w.])(?:[\w-]+[\\/])*[\w-]+\.[A-Za-z0-9]{1,16}(?!\w)")
_FILE_READ_ACTION = re.compile(r"\b(?:read|open|load|inspect|extract|parse)\b", re.IGNORECASE)
_STATISTICS_REQUEST = re.compile(r"\bstatistics?\b", re.IGNORECASE)


def required_tool_names(goal: str, tools: list[dict], documents: list[dict] | None = None) -> list[str]:
    """Identify enabled MCP tools explicitly needed by a narrowly recognizable goal."""
    available = {item.get("name") for item in tools}
    selected_names = {str(item.get("name", "")).casefold() for item in documents or []}
    named_files = {
        match.group(0).replace("\\", "/").rsplit("/", 1)[-1].casefold()
        for match in _NAMED_FILE.finditer(goal)
    }
    references_selected_document = bool(named_files & selected_names)
    required = []
    if ("read_text_file" in available and _NAMED_FILE.search(goal)
            and _FILE_READ_ACTION.search(goal) and not references_selected_document):
        required.append("read_text_file")
    if "calculate_statistics" in available and _STATISTICS_REQUEST.search(goal):
        required.append("calculate_statistics")
    return required


class AgentPlanner:
    async def create_plan(self, provider, model: str, goal: str, tools: list[dict], documents: list[dict],
            max_steps: int, require_tool: bool = False, correction: str | None = None) -> ExecutionPlan:
        system = """Create only a safe JSON execution plan. Do not provide prose, chain-of-thought, or private reasoning.
Return exactly {"goal": string, "steps": [{"step_number": integer, "type": "tool"|"rag"|"final", "title": string, "description": string|null, "tool_name": string|null, "arguments": object}]}.
The tools in available_tools are connected, enabled MCP workspace tools and are available for execution. Use only tool names supplied below. Never claim that a listed tool is inaccessible. selected_documents are already-ingested Knowledge Base documents, not MCP workspace files. Access selected_documents only with a rag step; never use read_text_file or analyze_text to read or analyze them. The final step can consume the retrieved excerpts directly. Add a rag step when selected_documents are supplied and the goal needs them. End with exactly one final step.
For a later tool argument that consumes an earlier result, use {"$from_step": N, "path": "field"}. To convert text file content into numbers use {"$from_step": N, "path": "content", "transform": "number_list"}.
Never invent a tool, result, file, document, or extra step. Keep the plan minimal.
When required_tool_use is true, the plan MUST contain appropriate tool steps followed by a final step. Include every tool named in required_tools. For a named text file whose numbers need statistics, first call read_text_file, then pass its actual content to calculate_statistics with the number_list step-reference transform. Never replace required tool execution with model calculation or a final-only answer."""
        required_tools = required_tool_names(goal, tools, documents)
        payload = {"goal": goal, "maximum_steps": max_steps,
            "required_tool_use": require_tool or bool(required_tools), "required_tools": required_tools,
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
            max_tool_calls: int, require_tool: bool = False,
            required_tools: list[str] | None = None) -> None:
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
        selected_tools = {step.tool_name for step in tool_steps}
        missing_tools = set(required_tools or ()) - selected_tools
        if missing_tools:
            raise AgentPlanError("Plan omitted a required available tool")
        if {"read_text_file", "calculate_statistics"}.issubset(required_tools or ()):
            read_steps = [step for step in tool_steps if step.tool_name == "read_text_file"]
            statistics_steps = [step for step in tool_steps if step.tool_name == "calculate_statistics"]
            consumes_file_result = any(
                read.step_number < statistics.step_number
                and statistics.arguments.get("numbers") == {
                    "$from_step": read.step_number, "path": "content", "transform": "number_list"}
                for read in read_steps for statistics in statistics_steps)
            if not consumes_file_result:
                raise AgentPlanError("Statistics must consume the actual text-file result")
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

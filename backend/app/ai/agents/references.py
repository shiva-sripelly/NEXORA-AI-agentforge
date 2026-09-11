import re
from typing import Any


class StepReferenceError(ValueError):
    pass


def references(value: Any):
    if isinstance(value, dict):
        if "$from_step" in value:
            yield value
        else:
            for child in value.values():
                yield from references(child)
    elif isinstance(value, list):
        for child in value:
            yield from references(child)


def validate_references(value: Any, current_step: int) -> None:
    for reference in references(value):
        allowed = {"$from_step", "path", "transform"}
        if set(reference) - allowed:
            raise StepReferenceError("Step reference contains unsupported fields")
        source = reference.get("$from_step")
        if not isinstance(source, int) or source < 1 or source >= current_step:
            raise StepReferenceError("Step reference must target an earlier step")
        path = reference.get("path", "")
        if not isinstance(path, str) or (path and not re.fullmatch(r"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*", path)):
            raise StepReferenceError("Step reference path is invalid")
        if reference.get("transform") not in (None, "number_list"):
            raise StepReferenceError("Step reference transform is invalid")


def _lookup(value: Any, path: str) -> Any:
    for part in filter(None, path.split(".")):
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            raise StepReferenceError("Referenced result path does not exist")
    return value


def _number_list(value: Any) -> list[float]:
    if isinstance(value, dict) and "content" in value:
        value = value["content"]
    if isinstance(value, list) and all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value):
        return value
    if not isinstance(value, str):
        raise StepReferenceError("Referenced value cannot be converted to numbers")
    tokens = re.findall(r"(?<![\w.])-?(?:\d+(?:\.\d+)?|\.\d+)(?![\w.])", value)
    if not tokens:
        raise StepReferenceError("Referenced text contains no numbers")
    return [float(token) for token in tokens]


def resolve_references(value: Any, results: dict[int, dict[str, Any]]) -> Any:
    if isinstance(value, dict):
        if "$from_step" in value:
            source = value["$from_step"]
            if source not in results:
                raise StepReferenceError("Referenced step has not completed")
            resolved = _lookup(results[source], value.get("path", ""))
            return _number_list(resolved) if value.get("transform") == "number_list" else resolved
        return {key: resolve_references(child, results) for key, child in value.items()}
    if isinstance(value, list):
        return [resolve_references(child, results) for child in value]
    return value

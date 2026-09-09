"""Schema-driven retrieval paths, preserving descriptions and composition constraints."""
from __future__ import annotations

import re
from typing import Any
from ..schema_service import OutputSchemaError, validator


def pointer(tokens) -> str:
    return "".join("/" + str(t).replace("~", "~0").replace("/", "~1") for t in tokens)


def expand(node: Any, root: Any, seen: frozenset[str] = frozenset()) -> Any:
    if not isinstance(node, dict) or "$ref" not in node:
        return node
    ref = node["$ref"]
    if ref in seen:
        return node  # Recursive paths are expanded one instance level at a time.
    if ref == "#":
        target = root
    elif ref.startswith("#/"):
        target = root
        try:
            for token in ref[2:].split("/"):
                target = target[token.replace("~1", "/").replace("~0", "~")]
        except (KeyError, TypeError) as exc:
            raise OutputSchemaError("Unresolvable local schema reference.") from exc
    else:
        def find(value):
            if isinstance(value, dict):
                if value.get("$anchor") == ref[1:] or value.get("$dynamicAnchor") == ref[1:]:
                    return value
                for child in value.values():
                    result = find(child)
                    if result is not None:
                        return result
            elif isinstance(value, list):
                for child in value:
                    result = find(child)
                    if result is not None:
                        return result
            return None
        target = find(root)
        if target is None:
            raise OutputSchemaError("Unresolvable schema anchor.")
    resolved = expand(target, root, seen | {ref})
    siblings = {k: v for k, v in node.items() if k != "$ref"}
    return {"allOf": [resolved, siblings]} if siblings else resolved


def properties(node: Any, root: Any) -> dict[str, Any]:
    node = expand(node, root)
    if not isinstance(node, dict):
        return {}
    out = dict(node.get("properties", {}))
    for key in ("allOf", "anyOf", "oneOf"):
        for branch in node.get(key, []):
            for name, child in properties(branch, root).items():
                if name in out:
                    out[name] = {key: [out[name], child]}
                else:
                    out[name] = child
    return out


def child_schema(node: Any, token: str | None, root: Any) -> Any:
    node = expand(node, root)
    if isinstance(node, bool):
        return node
    base = True
    if token is None:
        base = node.get("items", True)
        if isinstance(base, list):
            base = {"anyOf": base}
        if node.get("prefixItems"):
            base = {"anyOf": [*node["prefixItems"], base]}
        if "type" in node and "array" not in types(node):
            base = False
    else:
        matches = [child for pattern, child in node.get("patternProperties", {}).items() if re.search(pattern, token)]
        if token in node.get("properties", {}):
            matches.append(node["properties"][token])
        base = {"allOf": matches} if len(matches) > 1 else matches[0] if matches else node.get("additionalProperties", True)
        if "type" in node and "object" not in types(node):
            base = False
    constraints = [base]
    for key in ("allOf", "anyOf", "oneOf"):
        if key in node:
            # Branch choice is enforced on the completed instance, not a single leaf.
            op = "anyOf" if key == "oneOf" else key
            constraints.append({op: [child_schema(b, token, root) for b in node[key]]})
    return {"allOf": constraints} if len(constraints) > 1 else base


def at_path(root: Any, path: list[str | None]) -> Any:
    node = root
    for token in path:
        node = child_schema(node, token, root)
    return expand(node, root)


def types(node: Any) -> list[str]:
    if not isinstance(node, dict):
        return []
    kind = node.get("type", [])
    return [kind] if isinstance(kind, str) else kind


def instructions(node: Any, root: Any) -> dict[str, Any]:
    node = expand(node, root)
    if not isinstance(node, dict):
        return {}
    out = dict(node.get("x-extraction", {}))
    descriptions = [node.get("description", "")]
    for key in ("allOf", "anyOf", "oneOf"):
        for branch in node.get(key, []):
            child = instructions(branch, root)
            descriptions.append(child.pop("description", ""))
            for name, value in child.items():
                if name not in out:
                    out[name] = value
                elif out[name] != value:
                    # Conflicting transformations must not choose an arbitrary branch.
                    out[name] = None
    out["description"] = "\n".join(d for d in descriptions if d)
    if re.search(r"\b(full (source )?document|overall document|entire document|primary language|throughout the document)\b", out["description"], re.I):
        out.setdefault("scope", "document")
    return out


def is_valid(value: Any, node: Any, root: Any) -> bool:
    # Resolve internal references against the original root, including its dialect.
    try:
        return validator(root).evolve(schema=node).is_valid(value)
    except Exception as exc:
        raise OutputSchemaError("Schema validation could not resolve a supplied constraint.") from exc


def analyze(root: Any, max_depth: int = 32) -> list[dict[str, Any]]:
    plan = []
    def walk(node, path, depth, refs, dynamic_positions=None):
        dynamic_positions = dynamic_positions or []
        if depth > max_depth:
            return
        ref = node.get("$ref") if isinstance(node, dict) else None
        if ref and ref in refs:
            plan.append({"path": path, "schema": node, "recursive": True})
            return
        node = expand(node, root)
        # Do not repeat entire nested schemas at every ancestor in provider prompts.
        summary = {k: v for k, v in node.items() if k in ("type", "enum", "format", "description", "required", "additionalProperties")} if isinstance(node, dict) else node
        plan.append({"path": path, "schema": summary, "instructions": instructions(node, root)})
        if dynamic_positions:
            plan[-1]["dynamic_key_positions"] = dynamic_positions
        for name, child in properties(node, root).items():
            walk(child, [*path, name], depth + 1, refs | {ref} if ref else refs, dynamic_positions)
        if isinstance(node, dict) and ("array" in types(node) or "items" in node or "prefixItems" in node):
            walk(child_schema(node, None, root), [*path, None], depth + 1, refs | {ref} if ref else refs, dynamic_positions)
        if isinstance(node, dict) and (node.get("patternProperties") or isinstance(node.get("additionalProperties"), dict)):
            dynamic = node.get("additionalProperties", True)
            if node.get("patternProperties"):
                dynamic = {"anyOf": [*node["patternProperties"].values(), dynamic]}
            walk(dynamic, [*path, ""], depth + 1, refs | {ref} if ref else refs, [*dynamic_positions, len(path)])
    walk(root, [], 0, set())
    for index, field in enumerate(plan):
        field["field_id"] = f"f{index}"
    return plan

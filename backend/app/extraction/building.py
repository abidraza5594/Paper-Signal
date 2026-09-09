"""Deterministic final assembly. No model sees or rewrites final JSON."""
from __future__ import annotations

import json
from typing import Any

from ..schema_service import validator
from .entities import decision_key
from .schema import child_schema, expand, is_valid, pointer, properties, types
from .types import Decision
from .validation import relation_failures


ABSENT = object()


def resolve_conflicts(decisions: list[Decision]) -> None:
    groups: dict[tuple, list[Decision]] = {}
    for decision in decisions:
        if decision.accepted:
            groups.setdefault(decision_key(decision), []).append(decision)
    for group in groups.values():
        values = {json.dumps(d.candidate.value, sort_keys=True, ensure_ascii=False) for d in group}
        if len(values) > 1:
            for decision in group:
                decision.accepted = False
                decision.confidence = 0
                decision.reason = "unresolved_conflict"
        else:
            # Repeated citations at the same location are not independent verification.
            occurrences = len({d.candidate.source_id for d in group})
            for decision in group:
                decision.confidence = round(min(0.99, decision.confidence + min(0.03, (occurrences - 1) * 0.01)), 3)
    disputed_cells = set()
    for decision in decisions:
        c = decision.candidate
        if decision.reason == "unresolved_conflict" and c.column is not None:
            disputed_cells.add((tuple(c.path[:-1]), decision_key(decision)[1], c.source_id, c.column))
    for decision in decisions:
        c = decision.candidate
        # A count and a category can be derived from the same printed cell.
        # Do not keep one interpretation of that cell after contradictory
        # occurrences have made its interpretation uncertain.
        if decision.accepted and (tuple(c.path[:-1]), decision_key(decision)[1], c.source_id, c.column) in disputed_cells:
            decision.accepted = False
            decision.confidence = 0
            decision.reason = "ambiguous_shared_cell_evidence"


def build_json(schema: Any, decisions: list[Decision]) -> tuple[Any, list[str]]:
    chosen: dict[tuple, Decision] = {}
    for decision in decisions:
        if decision.accepted:
            chosen.setdefault(decision_key(decision), decision)

    def build(node, path, entities, output_path, depth=0):
        if depth > 64:
            return ABSENT
        key = (tuple(path), tuple(entities))
        if key in chosen:
            # Containers cannot be candidate values; descendants must each be proven.
            for d in decisions:
                if d.accepted and decision_key(d) == key:
                    d.field_path = pointer(output_path)
            return chosen[key].candidate.value
        descendants = [d for d in chosen.values() if d.candidate.path[:len(path)] == path
                       and list(decision_key(d)[1][:len(entities)]) == entities and len(d.candidate.path) > len(path)]
        node = expand(node, schema)
        if not descendants:
            if is_valid(None, node, schema):
                return None
            if is_valid([], node, schema):
                return []
            if is_valid({}, node, schema):
                return {}
        next_tokens = [d.candidate.path[len(path)] for d in descendants]
        is_array = None in next_tokens or "array" in types(node)
        if is_array:
            ids = list(dict.fromkeys(decision_key(d)[1][len(entities)] for d in descendants
                                    if len(decision_key(d)[1]) > len(entities)))
            result = []
            for entity in ids:
                item_node = child_schema(node, None, schema)
                if isinstance(node, dict) and len(result) < len(node.get("prefixItems", [])):
                    item_node = node["prefixItems"][len(result)]
                value = build(item_node, [*path, None], [*entities, entity], [*output_path, len(result)], depth + 1)
                if value is not ABSENT:
                    result.append(value)
            return result
        declared = properties(node, schema)
        if declared or any(t is not None for t in next_tokens) or "object" in types(node):
            result = {}
            names = list(dict.fromkeys([*declared, *(t for t in next_tokens if t is not None)]))
            for name in names:
                value = build(child_schema(node, name, schema), [*path, name], entities, [*output_path, name], depth + 1)
                if value is not ABSENT:
                    result[name] = value
            return result
        return ABSENT

    data = build(schema, [], [], [])
    if data is ABSENT:
        data = None
    # Declared relational contradictions reject involved facts together.
    for paths in relation_failures(data, schema):
        for decision in decisions:
            if decision.accepted and any(decision.field_path == p or (decision.field_path or "").startswith(p + "/") for p in paths):
                decision.accepted = False
                decision.reason = "cross_field_conflict"
                decision.confidence = 0
        return build_json(schema, decisions)

    errors = list(validator(schema).iter_errors(data))
    # Repair only by removing facts at failing subtrees, never by supplying replacements.
    invalid_paths = {pointer(e.absolute_path) for e in errors}
    removed = False
    for decision in decisions:
        if decision.accepted and any(p and (decision.field_path == p or (decision.field_path or "").startswith(p + "/")) for p in invalid_paths):
            decision.accepted = False
            decision.reason = "final_schema_constraint"
            decision.confidence = 0
            removed = True
    if removed:
        return build_json(schema, decisions)
    return data, sorted(invalid_paths)


def grounding_errors(data: Any, decisions: list[Decision]) -> list[str]:
    """An independent final leaf audit catches assembly or remapping bugs."""
    accepted = {d.field_path: d for d in decisions if d.accepted and d.field_path is not None}
    errors = []
    def walk(value, path):
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, [*path, key])
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, [*path, index])
        elif value is not None:
            field = pointer(path)
            decision = accepted.get(field)
            if decision is None or type(value) is not type(decision.candidate.value) or value != decision.candidate.value:
                errors.append(field)
    walk(data, [])
    return errors

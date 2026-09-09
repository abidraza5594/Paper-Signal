"""Resolve repeated entities only through schema-declared strong identifiers."""
from __future__ import annotations

import json
import re

from .schema import at_path, instructions
from .types import Decision


def resolve_identities(decisions: list[Decision], schema, identity_paths=()) -> None:
    # x-extraction.identity=true on a scalar explicitly designates a strong ID.
    # Similar labels alone never establish identity, even when other fields match.
    aliases: dict[tuple, tuple[str, ...]] = {}
    for decision in decisions:
        c = decision.candidate
        if not decision.accepted or not c.entity_ids:
            continue
        policy = instructions(at_path(schema, c.path), schema)
        if (policy.get("identity") is not True and c.path not in identity_paths) or not isinstance(c.value, str) or not c.value.strip():
            continue
        scope = (tuple(c.path), tuple(c.entity_ids[:-1]), c.value)
        aliases.setdefault(scope, tuple(c.entity_ids))
    entity_aliases = {}
    for decision in decisions:
        c = decision.candidate
        if decision.accepted and c.entity_ids and (instructions(at_path(schema, c.path), schema).get("identity") is True or c.path in identity_paths):
            scope = (tuple(c.path), tuple(c.entity_ids[:-1]), c.value)
            if scope in aliases:
                array_path = tuple(c.path[:len(c.path) - list(reversed(c.path)).index(None)])
                entity_aliases[(array_path, tuple(c.entity_ids))] = aliases[scope]
    for decision in decisions:
        c = decision.candidate
        ids = list(c.entity_ids)
        depth = 0
        for index, token in enumerate(c.path):
            if token is None:
                depth += 1
                alias = entity_aliases.get((tuple(c.path[:index + 1]), tuple(ids[:depth])))
                if alias:
                    ids[:depth] = alias
        decision.resolved_entity_ids = tuple(ids)
    # Explicit set semantics can deduplicate primitive values without asserting
    # that two business entities with similar labels are the same entity.
    values = {}
    for decision in decisions:
        c = decision.candidate
        if not decision.accepted or not c.path or c.path[-1] is not None:
            continue
        node = at_path(schema, c.path[:-1])
        unique = isinstance(node, dict) and node.get("uniqueItems") is True
        unique = unique or bool(re.search(r"^\s*unique\b", instructions(node, schema).get("description", ""), re.I))
        if not unique:
            continue
        ids = decision.resolved_entity_ids or tuple(c.entity_ids)
        scope = (tuple(c.path), ids[:-1], json.dumps(c.value, ensure_ascii=False, sort_keys=True))
        values.setdefault(scope, ids)
        decision.resolved_entity_ids = values[scope]

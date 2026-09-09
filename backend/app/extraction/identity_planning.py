"""Interpret explicit unique-collection descriptions; never merge on display labels."""
from __future__ import annotations

import json
import re

from .schema import at_path, instructions, types


def plan_unique_identities(schema, plan, model):
    collections = []
    eligible = {}
    result = []
    for field in plan:
        path = field["path"]
        node = at_path(schema, path)
        description = instructions(node, schema).get("description", "")
        if "array" not in types(node) or not re.search(r"^\s*unique\b", description, re.I):
            continue
        if "object" not in types(at_path(schema, [*path, None])):
            continue
        resolution = {"array_path": path, "identity_path": None,
                      "reason": "No unambiguous schema-defined identifier was established for this unique collection."}
        result.append(resolution)
        keys = []
        for child in plan:
            child_path = child["path"]
            if len(child_path) != len(path) + 2 or child_path[:-1] != [*path, None]:
                continue
            leaf = at_path(schema, child_path)
            policy = instructions(leaf, schema)
            if "string" not in types(leaf) or not (policy.get("identity") is True or re.search(r"\b(identifier|identification|code)\b", policy.get("description", ""), re.I)):
                continue
            keys.append({"field_id": child["field_id"], "path": child_path, "description": policy.get("description", ""), "explicit": policy.get("identity") is True})
        explicit = [key for key in keys if key["explicit"]]
        if len(explicit) == 1:
            resolution.update(identity_path=explicit[0]["path"], reason="Explicit x-extraction.identity declaration in the supplied schema.")
            continue
        if explicit:
            continue
        if keys:
            collections.append({"field_id": field["field_id"], "path": path, "description": description, "possible_identifiers": keys})
            eligible[field["field_id"]] = {key["field_id"]: key["path"] for key in keys}
    if not collections:
        return result
    response = model.extraction_json(json.dumps({"task": "schema_identity_plan", "collections": collections,
        "rules": [
            "Interpret the supplied schema descriptions ONLY. No document facts are requested.",
            "For each explicitly unique collection, identify at most one field whose description defines the identifier/code of that collection's actual entity.",
            "A currency, language, status, category, display name, measurement or shared attribute is NOT an entity identifier. Do not choose a field merely because it contains the word code.",
            "Select only when the identifier's described entity matches the unique collection's entity. Omit ambiguous collections and collections requiring a composite identifier.",
            "Return identities with array_field_id, identity_field_id, and reason explaining the matching entity and identifier descriptions.",
        ]}, ensure_ascii=False))
    items = response.get("identities", [])
    if not isinstance(items, list):
        return result
    for collection in collections:
        matches = [item for item in items if isinstance(item, dict) and item.get("array_field_id") == collection["field_id"]]
        if len(matches) == 1 and matches[0].get("identity_field_id") in eligible[collection["field_id"]]:
            resolution = next(entry for entry in result if entry["array_path"] == collection["path"])
            resolution.update(identity_path=eligible[collection["field_id"]][matches[0]["identity_field_id"]],
                              reason=str(matches[0].get("reason", "")))
    return result


def withhold_unidentified_unique_entities(decisions, identities):
    for identity in identities:
        prefix = [*identity["array_path"], None]
        depth = prefix.count(None)
        identified = {tuple(d.candidate.entity_ids[:depth]) for d in decisions
                      if d.accepted and d.candidate.path == identity["identity_path"]}
        for decision in decisions:
            c = decision.candidate
            if decision.accepted and c.path[:len(prefix)] == prefix and tuple(c.entity_ids[:depth]) not in identified:
                decision.accepted = False
                decision.confidence = 0
                decision.reason = "unresolved_unique_entity_identity"

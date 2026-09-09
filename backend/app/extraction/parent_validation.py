"""Validate described nested objects together, independently of their scalar types."""
from __future__ import annotations

import json

from .schema import at_path, instructions, types


def verify_described_parents(decisions, schema, windows, inventory, model, image_reader=None, crop_reader=None):
    groups = {}
    for decision in decisions:
        c = decision.candidate
        if not decision.accepted or len(c.path) < 3:
            continue
        parent_path = c.path[:-1]
        node = at_path(schema, parent_path)
        if "object" not in types(node) or not instructions(node, schema).get("description"):
            continue
        key = (tuple(parent_path), tuple(c.entity_ids), c.source_id)
        groups.setdefault(key, []).append(decision)
    for (path, entities, source_id), group in groups.items():
        window = windows[source_id]
        images = [image_reader(window.page)] if window.visual_required and image_reader else None
        if window.visual_required and crop_reader and window.bbox:
            images = [*(images or []), crop_reader(window.page, window.bbox)]
        question = {
            "index": 0, "source_id": source_id,
            "candidate": {"path": list(path), "entity_ids": list(entities),
                          "fields": [d.candidate.model_dump() for d in group]},
            "field_schema": at_path(schema, list(path)), "source": window.payload(),
            "document_opening_context": inventory[:2],
            "rules": [
                "Verify ONLY whether these facts belong to the PARENT OBJECT as defined by its description. Do not merely verify that each value has the right datatype or appears in the source.",
                "Identify the entity that the source block actually describes, then compare it to the entity requested by the parent description. Reject when the role/association is unstated or belongs to a different entity.",
                "Component values must not be borrowed from another entity's contact details, office, profile, account, product, location, or transaction. Agreement of one component does not establish the parent association.",
                "Explain the requested parent role and the source entity role in reason. Copy index, source_id and candidate.path into field_path. supported is true only if the parent association is explicit and consistent; visual_supported is false without images.",
            ],
        }
        response = model.extraction_json(json.dumps({"task": "Independent parent entity association audit.",
                                                     "questions": [question]}, ensure_ascii=False), images)
        verdicts = response.get("verdicts", [])
        matches = [v for v in verdicts if isinstance(v, dict) and type(v.get("index")) is int and v["index"] == 0
                   and v.get("source_id") == source_id and v.get("field_path") == list(path)] if isinstance(verdicts, list) else []
        verdict = matches[0] if len(matches) == 1 else {}
        supported = verdict.get("supported") is True and (not window.visual_required or bool(images) and verdict.get("visual_supported") is True)
        for decision in group:
            decision.verification["parent_association"] = verdict
            if not supported:
                decision.accepted = False
                decision.confidence = 0
                decision.reason = "parent_entity_verification_failed"

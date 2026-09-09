from __future__ import annotations

import re
from typing import Any

from .confidence import score
from .entities import association_valid
from .normalization import supported_value
from .schema import at_path, instructions, is_valid
from .types import Candidate, Decision, EvidenceWindow


def prevalidate(candidate: Candidate, windows: dict[str, EvidenceWindow], parents: dict[str, str | None], schema: Any, *, document_scope: bool = False) -> Decision:
    def reject(reason):
        return Decision(candidate, False, reason)
    window = windows.get(candidate.source_id)
    if window is None or window.page < 1:
        return reject("unknown_source")
    if not association_valid(candidate, window, parents):
        return reject("invalid_entity_association")
    if candidate.quote not in window.text or candidate.raw_value not in candidate.quote:
        return reject("evidence_not_exact")
    boundary = (r"(?<!\w)" if candidate.raw_value[0].isalnum() else "") + re.escape(candidate.raw_value) + (r"(?!\w)" if candidate.raw_value[-1].isalnum() else "")
    if not re.search(boundary, window.text):
        return reject("partial_token_not_supported")
    if window.cells:
        if candidate.column is None or not 0 <= candidate.column < len(window.cells):
            return reject("table_column_required")
        if candidate.raw_value != window.cells[candidate.column].raw:
            return reject("raw_value_not_in_exact_cell")
        if len(window.cells) != len(window.columns):
            return reject("table_alignment_uncertain")
    elif candidate.column is not None:
        return reject("column_without_table")
    node = at_path(schema, candidate.path)
    policy = instructions(node, schema)
    description = policy.get("description", "")
    # Description-defined standard code shapes are constraints even when callers
    # omit a JSON Schema pattern. This prevents an exact but irrelevant quote
    # from being accepted as a language/currency code.
    code_pattern = None
    if re.search(r"ISO\s*639\s*-\s*1", description, re.I):
        code_pattern = r"[a-z]{2}"
    elif re.search(r"ISO\s*4217", description, re.I):
        code_pattern = r"[A-Z]{3}"
    if code_pattern and (not isinstance(candidate.value, str) or not re.fullmatch(code_pattern, candidate.value)):
        return reject("description_code_format")
    if policy.get("scope") == "document" and not document_scope:
        return reject("requires_document_wide_verification")
    if not is_valid(candidate.value, node, schema):
        return reject("schema_constraint")
    supported, normalization = supported_value(candidate.raw_value, candidate.value, policy)
    if normalization == "case_normalization" and re.search(r"\bexactly as printed\b", description, re.I):
        return reject("source_spelling_required")
    if not supported and document_scope and policy.get("scope") == "document" and isinstance(candidate.value, str) and re.search(r"\b(type|classif\w*|language|code|categor\w*)\b", policy.get("description", ""), re.I):
        supported, normalization = True, "document_scope_classification"
    if not supported:
        return reject(normalization)
    return Decision(candidate, True, "awaiting_semantic_verification", normalization=normalization)


def finish_verification(decision: Decision, window: EvidenceWindow, verified: bool, visual_verified: bool) -> Decision:
    if not verified or (window.visual_required and not visual_verified):
        decision.accepted = False
        decision.reason = "visual_verification_failed" if window.visual_required else "semantic_verification_failed"
        return decision
    candidate = decision.candidate
    last_name = next((t for t in reversed(candidate.path) if t is not None), "")
    canonical = lambda value: re.sub(r"[\W_]", "", value.casefold())
    label_match = bool(candidate.label and canonical(candidate.label) == canonical(last_name)
                       and candidate.label in candidate.quote
                       and candidate.quote.index(candidate.label) < candidate.quote.index(candidate.raw_value))
    table_match = bool(window.cells and candidate.column is not None
                       and canonical(window.columns[candidate.column]) == canonical(last_name))
    decision.confidence = score(table_match=table_match, label_match=label_match, quality=window.quality,
                                visual=visual_verified, normalized=decision.normalization != "none")
    decision.accepted = decision.confidence >= 0.60
    decision.reason = "accepted" if decision.accepted else "low_source_quality"
    return decision


def relation_failures(data: Any, schema: Any) -> list[list[str]]:
    """Only schema-declared relations; never infer totals or units from field names."""
    failures = []
    if not isinstance(schema, dict):
        return failures
    def read(path):
        value = data
        for token in path.strip("/").split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            value = value[int(token)] if isinstance(value, list) else value[token]
        return value
    for rule in schema.get("x-extraction", {}).get("relations", []):
        try:
            left = read(rule["left"])
            right = read(rule["right"])
            if left is None or right is None:
                continue
            op = rule["operator"]
            valid = {"le": lambda: left <= right, "ge": lambda: left >= right,
                     "eq": lambda: left == right, "sum_eq": lambda: sum(left) == right}[op]()
            if not valid:
                failures.append([rule["left"], rule["right"]])
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    return failures

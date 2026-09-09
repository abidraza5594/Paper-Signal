from __future__ import annotations

from .types import Candidate, Decision, EvidenceWindow


def association_valid(candidate: Candidate, window: EvidenceWindow, parents: dict[str, str | None]) -> bool:
    if candidate.path.count(None) != len(candidate.entity_ids):
        return False
    lineage = []
    current: str | None = window.entity_id
    while current is not None and current not in lineage:
        lineage.append(current)
        current = parents.get(current)
    previous = len(lineage)
    for entity in candidate.entity_ids:
        if entity not in lineage or entity == "document":
            return False
        position = lineage.index(entity)
        if position >= previous:
            return False
        previous = position
    # An array item extracted from a table row must use that row as its innermost
    # identity. A table/page id would otherwise collapse all rows into one object.
    if candidate.entity_ids and candidate.entity_ids[-1] != window.entity_id:
        return False
    return True


def candidate_key(candidate: Candidate) -> tuple:
    return tuple(candidate.path), tuple(candidate.entity_ids)


def decision_key(decision: Decision) -> tuple:
    return tuple(decision.candidate.path), decision.resolved_entity_ids if decision.resolved_entity_ids is not None else tuple(decision.candidate.entity_ids)

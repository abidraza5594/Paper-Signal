from .types import Decision, EvidenceWindow


def record(decision: Decision, windows: dict[str, EvidenceWindow]) -> dict:
    candidate = decision.candidate
    window = windows.get(candidate.source_id)
    return {
        "fieldPath": decision.field_path,
        "schemaPath": candidate.path,
        "candidateValue": candidate.value,
        "rawValue": candidate.raw_value,
        "evidenceBinding": candidate.evidence_binding,
        "sourceId": candidate.source_id,
        "sourcePage": window.page if window else None,
        "sourceSection": window.section if window else None,
        "sourceTable": window.table_id if window else None,
        "sourceColumn": candidate.column,
        "sourceLabel": candidate.label,
        "sourceParser": window.parser if window else None,
        "rowId": window.row_id if window else None,
        "sourceBbox": window.bbox if window else None,
        "entityIds": candidate.entity_ids,
        "resolvedEntityIds": decision.resolved_entity_ids,
        "evidenceText": candidate.quote,
        "confidence": decision.confidence,
        "normalizationApplied": decision.normalization,
        "verification": decision.verification,
        "accepted": decision.accepted,
        "rejectionReason": None if decision.accepted else decision.reason,
    }

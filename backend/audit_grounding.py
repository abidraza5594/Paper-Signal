"""Recheck a saved live result against a freshly parsed document, without an AI call."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.extraction.schema import pointer
from app.extraction.types import Candidate
from app.extraction.validation import prevalidate
from app.pdf_service import PdfTextService
from app.schema_service import validator


def audit_result(pdf: Path, result: dict) -> dict:
    document = PdfTextService().extract(pdf)
    windows = {w.id: w for page in document.pages if page.layout for w in page.layout.windows}
    parents = {key: value for page in document.pages if page.layout for key, value in page.layout.parents.items()}
    provenance = result.get("provenance", [])
    failures = []
    for entry in provenance:
        window = windows.get(entry["sourceId"])
        if window is None:
            failures.append({"path": entry["fieldPath"], "reason": "source_not_in_native_parse_requires_transcription_audit"})
            continue
        column = entry.get("sourceColumn")
        if "sourceColumn" not in entry:
            matches = [cell.column for cell in window.cells if cell.raw == entry["rawValue"]]
            if len(matches) > 1:
                failures.append({"path": entry["fieldPath"], "reason": "legacy_provenance_has_ambiguous_column"})
                continue
            column = matches[0] if matches else None
        candidate = Candidate(path=entry["schemaPath"], source_id=entry["sourceId"],
                              entity_ids=entry["entityIds"], value=entry["candidateValue"],
                              raw_value=entry["rawValue"], quote=entry["evidenceText"], column=column, label=entry.get("sourceLabel", ""))
        decision = prevalidate(candidate, windows, parents, result["schema"], document_scope=entry.get("scope") == "document")
        if not decision.accepted or entry["sourcePage"] != window.page:
            failures.append({"path": entry["fieldPath"], "reason": decision.reason})
        if "verification" in entry:
            verdict = entry["verification"]
            if (verdict.get("supported") is not True or verdict.get("source_id") != entry["sourceId"]
                    or verdict.get("field_path") != entry["schemaPath"]
                    or (window.visual_required and verdict.get("visual_supported") is not True)):
                failures.append({"path": entry["fieldPath"], "reason": "missing_or_mismatched_verification"})
            parent = verdict.get("parent_association")
            if parent is not None and (parent.get("supported") is not True or parent.get("source_id") != entry["sourceId"]
                    or parent.get("field_path") != entry["schemaPath"][:-1]
                    or (window.visual_required and parent.get("visual_supported") is not True)):
                failures.append({"path": entry["fieldPath"], "reason": "missing_or_mismatched_parent_association"})
    populated = []
    def visit(value, path):
        if isinstance(value, dict):
            for key, child in value.items():
                visit(child, [*path, key])
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, [*path, index])
        elif value is not None:
            name = pointer(path)
            populated.append(name)
            if not any(p["fieldPath"] == name and type(p["candidateValue"]) is type(value) and p["candidateValue"] == value for p in provenance):
                failures.append({"path": name, "reason": "missing_provenance"})
    visit(result["data"], [])
    return {"schema_valid": validator(result["schema"]).is_valid(result["data"]),
            "populated_fields": len(populated), "source_records": len(provenance),
            "mechanical_grounding_failures": failures,
            "semantic_correctness": "Requires independent source review; exact evidence alone is insufficient."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("results", nargs="+", type=Path)
    args = parser.parse_args()
    for path in args.results:
        result = audit_result(args.pdf, json.loads(path.read_text(encoding="utf-8")))
        print(json.dumps({"file": str(path), **result}, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()

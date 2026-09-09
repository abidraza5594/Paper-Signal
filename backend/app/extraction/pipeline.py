from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from .building import build_json, grounding_errors, resolve_conflicts
from .layout import transcribed_layout
from .llm import ExtractionModel, candidates_prompt, verification_prompt
from .provenance import record
from .retrieval import evidence_mapping
from .schema import analyze, at_path, instructions
from .types import Candidate, Decision, EvidenceWindow, ExtractionOutcome
from .validation import finish_verification, prevalidate
from .entity_resolution import resolve_identities
from .parent_validation import verify_described_parents
from .identity_planning import plan_unique_identities, withhold_unidentified_unique_entities


logger = logging.getLogger(__name__)


class GroundedExtractionPipeline:
    def __init__(self, model: ExtractionModel, *, window_chars: int = 16000, max_candidates: int = 5000,
                 verification_batch_size: int = 12):
        self.model = model
        self.window_chars = window_chars
        self.max_candidates = max_candidates
        self.verification_batch_size = verification_batch_size

    def run(self, document, schema: Any, *, image_reader: Callable[[int], str] | None = None, crop_reader=None,
            progress: Callable[[int, str], None] | None = None, debug: bool = False) -> ExtractionOutcome:
        plan = analyze(schema)
        unique_identities = plan_unique_identities(schema, plan, self.model)
        field_paths = {field["field_id"]: field["path"] for field in plan}
        dynamic_positions = {field["field_id"]: field.get("dynamic_key_positions", []) for field in plan}
        def parse_candidate(item):
            if isinstance(item, dict) and "field_id" in item:
                item = dict(item)
                field_id = item.pop("field_id")
                if field_id not in field_paths:
                    raise ValueError("Unknown schema field ID")
                item["path"] = list(field_paths[field_id])
                keys = item.pop("dynamic_keys", [])
                if len(keys) != len(dynamic_positions[field_id]):
                    raise ValueError("Dynamic property keys do not match the schema path")
                for position, key in zip(dynamic_positions[field_id], keys):
                    item["path"][position] = key
                if item["path"].count(None) == 1 and item.get("source_id") in windows:
                    item["entity_ids"] = [windows[item["source_id"]].entity_id]
                window = windows.get(item.get("source_id"))
                if window is not None:
                    column = item.get("column")
                    if window.cells and type(column) is int and 0 <= column < len(window.cells):
                        raw = window.cells[column].raw
                        if raw and len(raw) <= 4000 and len(window.text) <= 8000:
                            item.update(raw_value=raw, quote=window.text, evidence_binding="source_cell")
                    elif not window.cells and column is None:
                        # A model chooses an existing source, never authors the raw fact.
                        # Retain an exact proposed span where possible; otherwise bind
                        # to the full source window and re-run all value/meaning gates.
                        raw = item.get("raw_value")
                        if isinstance(raw, str) and raw and raw in window.text and len(window.text) <= 8000:
                            item.update(quote=window.text, evidence_binding="source_span")
                        elif len(window.text) <= 4000:
                            item.update(raw_value=window.text, quote=window.text, evidence_binding="source_window")
            return Candidate.model_validate(item)
        windows: dict[str, EvidenceWindow] = {}
        parents: dict[str, str | None] = {}
        inventory = []
        for page in document.pages:
            layout = page.layout or transcribed_layout(page.text, page.number, "text")
            windows.update({w.id: w for w in layout.windows})
            parents.update(layout.parents)
            inventory.append({"page": page.number, "headings": layout.headings,
                              "tables": [{"id": t.id, "heading": t.heading, "columns": t.columns, "parent_id": t.parent_id} for t in layout.tables],
                              "images": len(layout.image_boxes), "read_complete": not page.needs_ocr,
                              "window_count": len(layout.windows),
                              "opening_context": page.text[:1800] if page.number <= 2 else ""})
        mapping = evidence_mapping(plan, list(windows.values()))
        decisions: list[Decision] = []
        warnings: list[str] = []
        document_text = [{"page": page.number, "sources": [{"id": w.id, "text": w.text}
                         for w in windows.values() if w.page == page.number]} for page in document.pages]
        complete_context_available = sum(len(w.text) for w in windows.values()) <= 64000
        batches: list[list[EvidenceWindow]] = []
        batch: list[EvidenceWindow] = []
        size = 0
        for window in windows.values():
            # Never silently truncate a table row. An oversized window is unresolved.
            if len(window.text) > self.window_chars:
                warnings.append(f"Source window {window.id} exceeds the local evidence limit; search incomplete.")
                continue
            if batch and (size + len(window.text) > self.window_chars or len(batch) >= 100):
                batches.append(batch)
                batch, size = [], 0
            batch.append(window)
            size += len(window.text)
        if batch:
            batches.append(batch)
        def extract_local(batch, focus=None):
            try:
                return self.model.extraction_json(candidates_prompt(schema, plan, batch, inventory, mapping, focus))
            except Exception as exc:
                if getattr(exc, "failure_code", "") not in ("AI_INVALID_CANDIDATES", "AI_OUTPUT_TRUNCATED"):
                    raise
                if len(batch) <= 1:
                    warnings.append(f"Candidate generation failed for source {batch[0].id}; search incomplete.")
                    return {"candidates": []}
                middle = len(batch) // 2
                left = extract_local(batch[:middle], {"reason": "Previous response was invalid; re-read this smaller source window."})
                right = extract_local(batch[middle:], {"reason": "Previous response was invalid; re-read this smaller source window."})
                return {"candidates": [*left.get("candidates", []), *right.get("candidates", [])]}
        for index, batch in enumerate(batches):
            payload = extract_local(batch)
            items = payload.get("candidates", [])
            if not isinstance(items, list):
                warnings.append(f"Candidate response invalid in evidence batch {index + 1}; search incomplete.")
                continue
            for item in items:
                if len(decisions) >= self.max_candidates:
                    warnings.append("Candidate limit reached; search incomplete.")
                    break
                try:
                    candidate = parse_candidate(item)
                    if candidate.source_id not in {w.id for w in batch}:
                        decisions.append(Decision(candidate, False, "source_outside_window"))
                        continue
                    decisions.append(prevalidate(candidate, windows, parents, schema))
                except (ValidationError, TypeError, ValueError):
                    warnings.append(f"Malformed candidate rejected in batch {index + 1}.")
            if progress:
                progress(35 + int((index + 1) / max(1, len(batches)) * 25), f"Searching evidence {index + 1} of {len(batches)}")

        # Targeted recovery is bounded, changes context, and can only propose new
        # candidates which pass the same gates. Never relax a rejected constraint.
        retried = set()
        for previous in list(decisions):
            if previous.accepted or previous.reason not in ("evidence_not_exact", "table_column_required", "raw_value_not_in_exact_cell"):
                continue
            key = (previous.candidate.source_id, tuple(previous.candidate.path))
            if key in retried or len(retried) >= 12 or len(decisions) >= self.max_candidates:
                continue
            retried.add(key)
            window = windows[previous.candidate.source_id]
            payload = extract_local([window], {"field": previous.candidate.path, "reason": previous.reason,
                                               "instruction": "Re-read only this source and return corrected evidence, or no candidate."})
            for item in payload.get("candidates", []):
                try:
                    candidate = parse_candidate(item)
                    if candidate.path == previous.candidate.path and candidate.source_id == window.id:
                        decisions.append(prevalidate(candidate, windows, parents, schema))
                except (ValidationError, TypeError, ValueError):
                    continue

        # Re-read unique-collection rows with a focused item schema. This recovers
        # identifiers and missed fields without mixing neighboring rows.
        for identity in unique_identities:
            prefix = [*identity["array_path"], None]
            key_path = identity["identity_path"]
            if key_path is None:
                continue
            sources = list(dict.fromkeys(d.candidate.source_id for d in decisions if d.accepted
                and d.candidate.path[:len(prefix)] == prefix
                and windows[d.candidate.source_id].cells))
            keys = {d.candidate.value for d in decisions if d.accepted and d.candidate.path == key_path
                    and isinstance(d.candidate.value, str)}
            key_columns = {(windows[d.candidate.source_id].table_id, d.candidate.column) for d in decisions
                           if d.accepted and d.candidate.path == key_path and d.candidate.column is not None}
            for window in windows.values():
                for table_id, column in key_columns:
                    if window.table_id == table_id and column < len(window.cells):
                        raw = window.cells[column].raw
                        header_text = {cell for header in window.table_context[:2] for cell in header}
                        if raw and raw not in window.columns and raw not in header_text:
                            keys.add(raw)
            # Find repeated printed identifiers even when the broad first pass
            # omitted that row; otherwise contradictory occurrences go unseen.
            related = [window.id for window in windows.values() if window.cells and any(cell.raw in keys for cell in window.cells)]
            sources = list(dict.fromkeys([*sources, *related]))
            if len(sources) > 160:
                warnings.append("Repeated-entity review exceeded its row limit; some occurrences remain unchecked.")
                sources = sources[:160]
            row_plan = [field for field in plan if len(field["path"]) == len(prefix) + 1 and field["path"][:-1] == prefix]
            for start in range(0, len(sources), 20):
                if len(decisions) >= self.max_candidates:
                    break
                source_ids = sources[start:start + 20]
                request = candidates_prompt(schema, row_plan, [windows[sid] for sid in source_ids], inventory, mapping,
                    {"identity_path": key_path,
                     "numeric_component_fields": [f["field_id"] for f in row_plan if re.search(r"\b(number of|number only|numeric value only)\b", f.get("instructions", {}).get("description", ""), re.I)],
                     "instruction": "Re-read each exact table row using ONLY this focused item schema. Extract its printed identifier and supported requested fields. For numeric_component_fields, the description authorizes extracting the sole printed numeral from an alphanumeric label as a numeric value; retain the whole cell as raw evidence. Never count or invent unprinted numbers, or use a neighboring row's key or measurements. Omit fields absent from that row."})
                payload = self.model.extraction_json(request)
                for item in payload.get("candidates", []):
                    if len(decisions) >= self.max_candidates:
                        break
                    try:
                        candidate = parse_candidate(item)
                        if candidate.path in [field["path"] for field in row_plan] and candidate.source_id in source_ids:
                            decisions.append(prevalidate(candidate, windows, parents, schema))
                    except (ValidationError, TypeError, ValueError):
                        continue

        # Document-wide interpretations use the complete structural inventory,
        # not whichever local page happened to contain a matching word.
        global_fields = [f for f in plan if f.get("instructions", {}).get("scope") == "document" and None not in f["path"]]
        if global_fields and not complete_context_available:
            warnings.append("Document-wide interpretation withheld: complete readable text exceeds the verification context limit.")
        if global_fields and complete_context_available and all(not p.needs_ocr for p in document.pages):
            import json
            anchors = []
            for page in document.pages:
                page_windows = [w for w in windows.values() if w.page == page.number]
                anchors.extend(page_windows[:2])
            if anchors:
                request = json.loads(candidates_prompt(schema, global_fields, anchors, inventory, mapping))
                request["task"] = "Propose ONLY requested document-wide interpretations from the COMPLETE structural inventory and page anchors. Every page is represented. Use an applicable mixed category when multiple major types are present, or omit when uncertain. Cite an exact anchor quote; never infer absent facts."
                request["complete_document_text"] = document_text
                request["rules"].append("For document-wide interpretations, assess the complete_document_text from ALL pages. A local section title cannot establish the overall type. Consider major differences between sections and choose a supported mixed category or omit the field.")
                request["rules"].append("Return at most one document-wide candidate per field, citing the strongest representative anchor. Omit unresolved interpretations instead of emitting alternatives.")
                request["rules"] = [rule for rule in request["rules"] if "Do not classify a full document" not in rule]
                payload = self.model.extraction_json(json.dumps(request, ensure_ascii=False))
                for item in payload.get("candidates", []):
                    try:
                        candidate = parse_candidate(item)
                        if candidate.path in [f["path"] for f in global_fields] and candidate.source_id in {w.id for w in anchors}:
                            decisions.append(prevalidate(candidate, windows, parents, schema, document_scope=True))
                    except (ValidationError, TypeError, ValueError):
                        continue
                # Literal schema enum values are reproducible retrieval hints.
                # Recover a printed canonical value when a model proposes an
                # unsupported abbreviation; the full-document verifier still
                # decides whether that literal means the requested field.
                for field in global_fields:
                    node = field.get("schema")
                    for value in node.get("enum", []) if isinstance(node, dict) else []:
                        if not isinstance(value, str) or len(value) < 3:
                            continue
                        if any(d.accepted and d.candidate.path == field["path"] and d.candidate.value == value for d in decisions):
                            continue
                        if len(decisions) >= self.max_candidates:
                            break
                        pattern = re.compile(r"(?<!\w)" + re.escape(value) + r"(?!\w)")
                        for window in windows.values():
                            if len(window.text) > 8000 or not pattern.search(window.text):
                                continue
                            columns = [cell.column for cell in window.cells if cell.raw and pattern.search(cell.raw)]
                            column = columns[0] if columns else None
                            raw = window.cells[column].raw if column is not None else value
                            if window.cells and column is None or len(raw) > 4000:
                                continue
                            candidate = Candidate(path=field["path"], source_id=window.id, value=value,
                                raw_value=raw, quote=window.text, column=column, evidence_binding="literal_schema_enum")
                            decision = prevalidate(candidate, windows, parents, schema, document_scope=True)
                            if decision.accepted:
                                decisions.append(decision)
                                break

        valid = sorted((d for d in decisions if d.accepted), key=lambda d: windows[d.candidate.source_id].page)
        # Batch independent verification prompts to avoid a network request per scalar.
        for start in range(0, len(valid), self.verification_batch_size):
            group = valid[start:start + self.verification_batch_size]
            by_page: dict[int, list[Decision]] = {}
            for decision in group:
                by_page.setdefault(windows[decision.candidate.source_id].page, []).append(decision)
            for page, page_group in by_page.items():
                images = None
                requires_visual = any(windows[d.candidate.source_id].visual_required for d in page_group)
                if requires_visual and image_reader:
                    images = [image_reader(page)]
                questions = []
                for decision in page_group:
                    window = windows[decision.candidate.source_id]
                    import json
                    question = json.loads(verification_prompt(decision.candidate, window, schema, inventory))
                    if instructions(at_path(schema, decision.candidate.path), schema).get("scope") == "document":
                        question["complete_document_text"] = document_text
                        question["rules"].append("Check complete_document_text from ALL pages. Reject a single document category supported only by one section when other substantial sections have different types. A matching section title is insufficient.")
                        question["rules"].append("When this field's description requests a document classification or language code, it authorizes classification of the complete text. The normalized category/code need not be literally printed. Verify the interpretation from the complete text and the representative source quote; do not require a printed language-code label.")
                    question["index"] = len(questions)
                    questions.append(question)
                if requires_visual and crop_reader:
                    # Add legible local crops, keeping the full page for context.
                    boxes = list(dict.fromkeys(windows[d.candidate.source_id].bbox for d in page_group
                                               if windows[d.candidate.source_id].bbox))
                    images = [*(images or []), *(crop_reader(page, box) for box in boxes[:6])]
                import json
                response = self.model.extraction_json(json.dumps({
                    "task": "Verify each explicitly indexed candidate independently. Copy its exact index, source_id and candidate.path into field_path. Return {verdicts: [{index, source_id, field_path, supported, visual_supported, reason}]}. Reject when the source does not support the requested field's meaning, even if the quote is exact.",
                    "questions": questions,
                }), images)
                verdicts = response.get("verdicts", [])
                for i, decision in enumerate(page_group):
                    matches = [v for v in verdicts if isinstance(v, dict) and type(v.get("index")) is int and v["index"] == i
                               and v.get("source_id") == decision.candidate.source_id
                               and v.get("field_path") == decision.candidate.path] if isinstance(verdicts, list) else []
                    verdict = matches[0] if len(matches) == 1 else {}
                    decision.verification = dict(verdict)
                    finish_verification(decision, windows[decision.candidate.source_id],
                                        verdict.get("supported") is True,
                                        bool(images) and verdict.get("visual_supported") is True)
            if progress:
                progress(60 + int(min(start + len(group), len(valid)) / max(1, len(valid)) * 30), "Verifying values against source evidence")
        verify_described_parents(decisions, schema, windows, inventory, self.model, image_reader, crop_reader)
        withhold_unidentified_unique_entities(decisions, unique_identities)
        resolve_identities(decisions, schema, [i["identity_path"] for i in unique_identities if i["identity_path"] is not None])
        from .source_consistency import withhold_source_disagreements
        withhold_source_disagreements(decisions, windows, schema,
            [i["identity_path"] for i in unique_identities if i["identity_path"] is not None])
        resolve_conflicts(decisions)
        data, errors = build_json(schema, decisions)
        errors.extend(grounding_errors(data, decisions))
        records = [record(d, windows) for d in decisions]
        for decision, entry in zip(decisions, records):
            for identity in unique_identities:
                prefix = [*identity["array_path"], None]
                if decision.candidate.path[:len(prefix)] == prefix:
                    entry["identitySchemaEvidence"] = identity["reason"]
            if decision.accepted and instructions(at_path(schema, decision.candidate.path), schema).get("scope") == "document":
                entry["consideredPages"] = [page.number for page in document.pages]
                entry["scope"] = "document"
                decision.confidence = min(decision.confidence, .80)
                entry["confidence"] = decision.confidence
        accepted = [r for r in records if r["accepted"] and r["fieldPath"] is not None]
        if any(p.needs_ocr for p in document.pages):
            warnings.append("Some pages remain unread or require visual interpretation; absence cannot be established.")
        if any(d.reason in {"unresolved_conflict", "unresolved_repeated_source_value"} for d in decisions):
            warnings.append("Contradictory candidates were withheld; see extraction audit.")
        if any(d.reason == "unresolved_unique_entity_identity" for d in decisions):
            warnings.append("Some unique-collection fragments lacked a verified entity identifier and were withheld.")
        if not accepted:
            warnings.append("No values passed evidence validation; this does not establish that the document lacks the requested information.")
        logger.info("extraction_completed pages=%d windows=%d candidates=%d accepted=%d schema_valid=%s",
                    len(document.pages), len(windows), len(decisions), len(accepted), not errors)
        return ExtractionOutcome(data, accepted, records, list(dict.fromkeys(warnings)), not errors, errors)

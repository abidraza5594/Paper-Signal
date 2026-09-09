import json
from dataclasses import replace

import fitz
import pytest

from app.extraction.building import build_json, grounding_errors, resolve_conflicts
from app.extraction.layout import PageLayout, native_layout, transcribed_layout
from app.extraction.normalization import supported_value
from app.extraction.pipeline import GroundedExtractionPipeline
from app.extraction.schema import analyze, at_path, is_valid
from app.extraction.types import Candidate, Cell, Decision, EvidenceWindow
from app.extraction.validation import finish_verification, prevalidate
from app.pdf_service import PageText, PdfTextResult, PdfTextService
from app.schema_service import parse_json_schema_contract, validator


def contract(properties, **kwargs):
    return {"type": "object", "properties": properties, "additionalProperties": False, **kwargs}


def candidate(path=None, value=42, raw="42", source="p1:t0:r0", entities=None, quote="A\t42", column=1):
    return Candidate(path=path or ["amount"], value=value, raw_value=raw, source_id=source,
                     entity_ids=entities or [], quote=quote, column=column)


def row(rid="p1:t0:r0", parent="p1:t0", amount="42", label="A", page=1):
    return EvidenceWindow(rid, page, f"{label}\t{amount}", rid, parent,
                          table_id=parent, row_id=rid, columns=["code", "amount"],
                          cells=[Cell(0, label), Cell(1, amount)], parser="pymupdf")


def accepted(c):
    return Decision(c, True, "accepted", .95)


@pytest.mark.parametrize("raw,value,policy,ok", [
    ("42", 42, {}, True), ("42", 43, {}, False), ("-4.25", -4.25, {}, True),
    ("1,234", 1234, {}, False), ("1,234", 1234, {"thousandsSeparator": ","}, True),
    ("1.234,50", 1234.5, {"thousandsSeparator": ".", "decimalSeparator": ","}, True),
    ("12,34", 1234, {"thousandsSeparator": ","}, False),
    ("42 kg", 42, {}, False), ("42 kg", 42, {"description": "numeric value only"}, True),
    ("4-8", 4, {}, False), ("Second", 1, {}, False), ("Second", 2, {}, False),
    ("Ground", 0, {}, False), ("First", 0, {"valueMap": {"First": 0}}, True),
    ("03/04/2024", "2024-03-04", {}, False),
    ("03/04/2024", "2024-04-03", {"dateFormat": "%d/%m/%Y"}, True),
    ("31/02/2024", "2024-02-29", {"dateFormat": "%d/%m/%Y"}, False),
    ("yes", True, {}, False), ("true", True, {}, True),
    ("Indoor theatre", True, {"description": "True if explicitly mentioned."}, True),
    ("open", "OPEN", {}, True), ("open", "ACTIVE", {}, False),
    ("open", "ACTIVE", {"valueMap": {"open": "ACTIVE"}}, True),
    ("10", 0.1, {"scale": 0.01}, True), ("10", 11, {"scale": 0.01}, False),
    ("NaN", float("nan"), {}, False), ("42", True, {}, False),
])
def test_normalization_never_guesses(raw, value, policy, ok):
    assert supported_value(raw, value, policy)[0] is ok


@pytest.mark.parametrize("changes,reason", [
    ({"value": 43}, "numeric_literal"),
    ({"source_id": "p2:t0:r0"}, "unknown_source"),
    ({"quote": "A\t43"}, "evidence_not_exact"),
    ({"column": 0}, "raw_value_not_in_exact_cell"),
    ({"column": None}, "table_column_required"),
    ({"entity_ids": ["p1:t1:r0"], "path": ["rows", None, "amount"]}, "invalid_entity_association"),
])
def test_plausible_wrong_values_fail(changes, reason):
    window = row()
    c = candidate().model_copy(update=changes)
    decision = prevalidate(c, {window.id: window}, {window.id: window.parent_id, window.parent_id: "p1", "p1": "document"},
                           contract({"amount": {"type": ["number", "null"]}}))
    assert not decision.accepted
    assert decision.reason == reason


def test_semantic_verifier_rejects_real_value_under_wrong_field():
    window = row()
    c = candidate(path=["differentMeaning"])
    decision = prevalidate(c, {window.id: window}, {window.id: window.parent_id},
                           contract({"differentMeaning": {"type": "number", "description": "Another measurement"}}))
    assert decision.accepted
    finish_verification(decision, window, verified=False, visual_verified=False)
    assert not decision.accepted


def test_scanned_candidate_requires_visual_agreement():
    window = replace(row(), visual_required=True, parser="ocr", quality=.65)
    d = accepted(candidate())
    assert not finish_verification(d, window, True, False).accepted
    assert finish_verification(accepted(candidate()), window, True, True).accepted


def test_nested_entities_cannot_cross_neighboring_tables():
    schema = contract({"groups": {"type": "array", "items": contract({"rows": {"type": "array", "items": contract({"amount": {"type": "number"}})}})}})
    decisions = []
    for t, amount in [(0, "42"), (1, "84")]:
        w = row(f"p1:t{t}:r0", f"p1:t{t}", amount)
        parents = {w.id: w.parent_id, w.parent_id: "p1", "p1": "document"}
        c = candidate(["groups", None, "rows", None, "amount"], int(amount), amount, w.id, [w.parent_id, w.id], w.text)
        d = prevalidate(c, {w.id: w}, parents, schema)
        assert d.accepted
        decisions.append(d)
        wrong = c.model_copy(update={"entity_ids": [f"p1:t{1-t}", w.id]})
        assert not prevalidate(wrong, {w.id: w}, parents, schema).accepted
    data, errors = build_json(schema, decisions)
    assert data == {"groups": [{"rows": [{"amount": 42}]}, {"rows": [{"amount": 84}]}]}
    assert not errors
    assert not grounding_errors(data, decisions)


def test_duplicate_labels_stay_distinct_and_repeated_citations_do_not_duplicate():
    schema = contract({"rows": {"type": "array", "items": contract({"code": {"type": "string"}})}})
    a = candidate(["rows", None, "code"], "A", "A", entities=["p1:t0:r0"], column=0)
    b = a.model_copy(update={"source_id": "p1:t0:r1", "entity_ids": ["p1:t0:r1"]})
    decisions = [accepted(a), accepted(a), accepted(b)]
    resolve_conflicts(decisions)
    data, errors = build_json(schema, decisions)
    assert data == {"rows": [{"code": "A"}, {"code": "A"}]}
    assert not errors


def test_conflicts_are_withheld_and_other_fields_survive():
    schema = contract({"amount": {"type": ["number", "null"]}, "code": {"type": "string"}})
    decisions = [accepted(candidate()), accepted(candidate(value=43, raw="43", source="p2:t0:r0")),
                 accepted(candidate(["code"], "A", "A", column=0))]
    resolve_conflicts(decisions)
    data, errors = build_json(schema, decisions)
    assert data == {"amount": None, "code": "A"}
    assert not errors
    assert decisions[0].reason == "unresolved_conflict"


def test_required_nonnullable_missing_reports_unsatisfied_without_invention():
    schema = contract({"amount": {"type": "number"}, "code": {"type": "string"}}, required=["amount", "code"])
    data, errors = build_json(schema, [accepted(candidate(["code"], "A", "A", column=0))])
    assert data == {"code": "A"}
    assert errors
    assert not validator(schema).is_valid(data)


def test_enum_format_additional_properties_and_composition():
    schema = contract({"record": {"$ref": "#/$defs/record"}}, **{"$defs": {"record": contract({
        "mode": {"enum": ["READY", None]}, "date": {"type": "string", "format": "date"},
        "size": {"allOf": [{"type": "integer"}, {"minimum": 2, "maximum": 8}]}
    })}})
    assert is_valid(3, at_path(schema, ["record", "size"]), schema)
    assert not is_valid(9, at_path(schema, ["record", "size"]), schema)
    assert not is_valid("2024-02-31", at_path(schema, ["record", "date"]), schema)
    assert not is_valid("GO", at_path(schema, ["record", "mode"]), schema)
    assert not is_valid("invented", at_path(schema, ["extra"]), schema)
    assert any(item["path"] == ["record", "date"] for item in analyze(schema))


@pytest.mark.parametrize("schema", [True, False, {"type": "array", "items": {"type": "number"}}, {"type": "string"},
                                        {"type": "object", "additionalProperties": {"type": "number"}},
                                        {"oneOf": [{"type": "string"}, {"type": "number"}]}])
def test_arbitrary_root_schemas_preserved(schema):
    assert parse_json_schema_contract(json.dumps(schema)).schema == schema


def test_cross_field_rules_are_schema_driven():
    schema = contract({"alpha": {"type": ["number", "null"]}, "beta": {"type": ["number", "null"]}},
                      **{"x-extraction": {"relations": [{"left": "/alpha", "right": "/beta", "operator": "le"}]}})
    data, errors = build_json(schema, [accepted(candidate(["alpha"], 8, "8")), accepted(candidate(["beta"], 4, "4"))])
    assert not errors
    assert not data or data == {"alpha": None, "beta": None}


def test_final_grounding_audit_detects_injected_leaf():
    decisions = [accepted(candidate())]
    data, _ = build_json(contract({"amount": {"type": "number"}}), decisions)
    data["invented"] = 19
    assert grounding_errors(data, decisions) == ["/invented"]


def test_two_native_tables_retain_geometry_and_do_not_reenter_prose(tmp_path):
    path = tmp_path / "two.pdf"
    doc = fitz.open()
    page = doc.new_page(width=600, height=400)
    for x, amount in [(40, "42"), (320, "84")]:
        for y in (60, 90, 120):
            page.draw_line((x, y), (x + 220, y))
        for xx in (x, x + 110, x + 220):
            page.draw_line((xx, 60), (xx, 120))
        page.insert_text((x + 10, 80), "code")
        page.insert_text((x + 120, 80), "amount")
        page.insert_text((x + 10, 110), "A")
        page.insert_text((x + 120, 110), amount)
    doc.save(path)
    doc.close()
    result = PdfTextService().extract(path)
    layout = result.pages[0].layout
    assert len(layout.tables) == 2
    assert all(c.bbox for t in layout.tables for r in t.rows for c in r)
    assert all(w.table_id for w in layout.windows)
    assert {t.rows[1][1].raw for t in layout.tables} == {"42", "84"}


def test_markdown_tables_and_continued_pages_keep_separate_identity():
    text = "# Chapter\n|code|amount|\n|---|---|\n|A|42|\n\n|code|amount|\n|---|---|\n|A|84|"
    first = transcribed_layout(text, 1, "ocr")
    second = transcribed_layout(text, 2, "ocr")
    assert len(first.tables) == 2
    assert not ({t.id for t in first.tables} & {t.id for t in second.tables})
    assert all(w.visual_required for w in first.windows)


class FakeModel:
    def __init__(self, candidates):
        self.candidates = candidates
        self.prompts = []

    def extraction_json(self, prompt, images=None):
        request = json.loads(prompt)
        self.prompts.append(request)
        if "questions" in request:
            return {"verdicts": [{"index": i, "supported": True, "visual_supported": bool(images),
                "source_id": q["candidate"]["source_id"], "field_path": q["candidate"]["path"], "reason": "fixture"}
                for i, q in enumerate(request["questions"])]}
        sources = {w["id"] for w in request["evidence_windows"]}
        return {"candidates": [c.model_dump() for c in self.candidates if c.source_id in sources]}


def test_pipeline_searches_later_pages_and_provenance_is_exact():
    a, b = row(), row("p2:t0:r0", "p2:t0", page=2)
    c = candidate(source=b.id)
    model = FakeModel([c])
    document = PdfTextResult([PageText(1, a.text, False, PageLayout([a], parents={a.id: a.parent_id})),
                              PageText(2, b.text, False, PageLayout([b], parents={b.id: b.parent_id}))], {})
    result = GroundedExtractionPipeline(model).run(document, contract({"amount": {"type": "number"}}), debug=True)
    assert result.data == {"amount": 42}
    assert result.schema_valid
    assert result.provenance[0]["sourcePage"] == 2
    assert result.provenance[0]["rawValue"] == "42"
    assert len(model.prompts[0]["document_inventory"]) == 2
    assert not result.warnings


def test_missing_ocr_response_does_not_mark_page_read():
    document = PdfTextResult([PageText(1, "", True), PageText(2, "", True)], {})
    changed = PdfTextService.apply_ocr(document, {1: "Recovered"})
    assert not changed.pages[0].needs_ocr
    assert changed.pages[1].needs_ocr


def test_classification_is_not_forced_from_a_local_page():
    schema = contract({"kind": {"type": ["string", "null"], "enum": ["MIXED", "REPORT", None],
                                "description": "Classify using the full document."}})
    window = row()
    c = candidate(["kind"], "REPORT", "42")
    decision = prevalidate(c, {window.id: window}, {window.id: window.parent_id}, schema)
    assert not decision.accepted


def test_description_code_constraint_rejects_exact_but_irrelevant_quote():
    schema = contract({"language": {"type": ["string", "null"],
                        "description": "ISO 639-1 code of the document's primary language."}})
    window = row(label="Unrelated Label")
    c = candidate(["language"], "Unrelated Label", "Unrelated Label", quote=window.text, column=0)
    decision = prevalidate(c, {window.id: window}, {window.id: window.parent_id}, schema, document_scope=True)
    assert not decision.accepted
    assert decision.reason == "description_code_format"


def test_verdict_cannot_be_applied_to_a_different_candidate():
    class MisboundModel(FakeModel):
        def extraction_json(self, prompt, images=None):
            response = super().extraction_json(prompt, images)
            for verdict in response.get("verdicts", []):
                verdict["field_path"] = ["other_field"]
            return response
    w = row()
    doc = PdfTextResult([PageText(1, w.text, False, PageLayout([w], parents={w.id: w.parent_id}))], {})
    outcome = GroundedExtractionPipeline(MisboundModel([candidate()])).run(
        doc, contract({"amount": {"type": ["number", "null"]}}), debug=True)
    assert not outcome.provenance
    assert all(d["rejectionReason"] == "semantic_verification_failed" for d in outcome.debug)


def test_document_classification_generation_and_verification_include_non_anchor_text():
    windows = [EvidenceWindow(f"p1:b{i}", 1, text, f"p1:b{i}", "p1")
               for i, text in enumerate(["Report", "Opening text", "Later section: prices and payment schedule"])]
    doc = PdfTextResult([PageText(1, "\n".join(w.text for w in windows), False,
        PageLayout(windows, parents={w.id: "p1" for w in windows}))], {})
    calls = []
    class Model:
        def extraction_json(self, prompt, images=None):
            request = json.loads(prompt)
            if "questions" in request:
                question = request["questions"][0]
                calls.append(question["complete_document_text"])
                return {"verdicts": [{"index": 0, "source_id": "p1:b0", "field_path": ["kind"],
                                      "supported": True, "visual_supported": False, "reason": "Mixed sections"}]}
            if "complete_document_text" in request:
                calls.append(request["complete_document_text"])
                return {"candidates": [{"field_id": "f1", "source_id": "p1:b0", "raw_value": "Report",
                                       "value": "MIXED", "quote": "Report", "entity_ids": []}]}
            return {"candidates": []}
    outcome = GroundedExtractionPipeline(Model()).run(doc, contract({"kind": {
        "type": ["string", "null"], "description": "Classify the full document.", "enum": ["MIXED", "REPORT", None]}}))
    assert outcome.data == {"kind": "MIXED"}
    assert len(calls) == 2
    assert all(context[0]["sources"][2]["text"].startswith("Later section") for context in calls)


def test_document_classification_abstains_when_complete_text_would_be_truncated():
    windows = [EvidenceWindow(f"p1:b{i}", 1, "a" * 9000, f"p1:b{i}", "p1") for i in range(8)]
    doc = PdfTextResult([PageText(1, "text", False, PageLayout(windows))], {})
    class Model:
        def extraction_json(self, prompt, images=None):
            assert "complete_document_text" not in json.loads(prompt)
            return {"candidates": []}
    outcome = GroundedExtractionPipeline(Model()).run(doc, contract({"kind": {
        "type": ["string", "null"], "description": "Classify the full document."}}))
    assert not outcome.provenance
    assert any("context limit" in warning for warning in outcome.warnings)


@pytest.mark.parametrize("value,expected", [(42, {"amount": 42}), (43, {})])
def test_server_binds_raw_cell_but_never_repairs_wrong_values(value, expected):
    window = row()
    doc = PdfTextResult([PageText(1, window.text, False, PageLayout([window], parents={window.id: window.parent_id}))], {})
    class Model:
        def extraction_json(self, prompt, images=None):
            request = json.loads(prompt)
            if "questions" in request:
                candidate = request["questions"][0]["candidate"]
                assert candidate["raw_value"] == "42" and candidate["quote"] == "A\t42"
                return {"verdicts": [{"index": 0, "source_id": window.id, "field_path": ["amount"],
                                      "supported": True, "visual_supported": False, "reason": "Exact amount column"}]}
            return {"candidates": [{"field_id": "f1", "source_id": window.id, "column": 1,
                                   "raw_value": "bad copied text", "quote": "invented quote", "value": value}]}
    outcome = GroundedExtractionPipeline(Model()).run(doc, contract({"amount": {"type": ["number", "null"]}}))
    assert outcome.data == expected
    if outcome.provenance:
        assert outcome.provenance[0]["evidenceBinding"] == "source_cell"


@pytest.mark.parametrize("supported", [True, False])
def test_literal_global_enum_recovery_still_requires_semantic_verification(supported):
    window = row(amount="TOKEN")
    doc = PdfTextResult([PageText(1, window.text, False, PageLayout([window], parents={window.id: window.parent_id}))], {})
    class Model:
        def extraction_json(self, prompt, images=None):
            request = json.loads(prompt)
            if "questions" in request:
                candidate = request["questions"][0]["candidate"]
                assert candidate["raw_value"] == "TOKEN" and candidate["column"] == 1
                return {"verdicts": [{"index": 0, "source_id": window.id, "field_path": ["kind"],
                                      "supported": supported, "visual_supported": False, "reason": "Checked field meaning"}]}
            return {"candidates": []}
    outcome = GroundedExtractionPipeline(Model()).run(doc, contract({"kind": {
        "type": ["string", "null"], "enum": ["TOKEN", None], "description": "Classification of the full document."}}))
    assert outcome.data == ({"kind": "TOKEN"} if supported else {})


def test_described_parent_rejects_other_entity_components_after_leaf_verification():
    from app.extraction.parent_validation import verify_described_parents
    schema = contract({"record": {"type": "object", "properties": {"location": {
        "type": "object", "description": "Physical location of the monitored device, excluding the supplier's office.",
        "properties": {"postalCode": {"type": "string"}, "country": {"type": "string"}}}}}})
    window = EvidenceWindow("p1:b0", 1, "Supplier office: 12345, Country A", "p1:b0", "p1")
    decisions = [accepted(Candidate(path=["record", "location", key], source_id=window.id, raw_value=value,
        value=value, quote=window.text)) for key, value in (("postalCode", "12345"), ("country", "Country A"))]
    class Model:
        def extraction_json(self, prompt, images=None):
            question = json.loads(prompt)["questions"][0]
            assert len(question["candidate"]["fields"]) == 2
            assert "monitored device" in question["field_schema"]["description"]
            return {"verdicts": [{"index": 0, "source_id": window.id, "field_path": ["record", "location"],
                                  "supported": False, "visual_supported": False, "reason": "Supplier office, not device location"}]}
    verify_described_parents(decisions, schema, {window.id: window}, [], Model())
    assert all(not d.accepted and d.reason == "parent_entity_verification_failed" for d in decisions)


@pytest.mark.parametrize("conflict", [False, True])
def test_unique_collection_recovers_row_identifiers_and_withholds_anonymous_fragments(conflict):
    schema = contract({"records": {"type": "array", "description": "Unique products recorded in the document.", "items": {
        "type": "object", "properties": {"code": {"type": "string", "description": "Printed product identifier code."},
        "amount": {"type": ["number", "null"]}}, "additionalProperties": False}}})
    windows = [row(label="Q", page=1), row(rid="p2:t0:r0", parent="p2:t0", label="Q", page=2, amount="43" if conflict else "42"),
               EvidenceWindow("p3:b0", 3, "42", "p3:b0", "p3")]
    doc = PdfTextResult([PageText(w.page, w.text, False, PageLayout([w], parents={w.id: w.parent_id})) for w in windows], {})
    fields = {tuple(f["path"]): f["field_id"] for f in analyze(schema)}
    class Model:
        def extraction_json(self, prompt, images=None):
            request = json.loads(prompt)
            if request.get("task") == "schema_identity_plan":
                return {"identities": [{"array_field_id": fields[("records",)],
                    "identity_field_id": fields[("records", None, "code")], "reason": "Product identifier matches unique product collection."}]}
            if "questions" in request:
                return {"verdicts": [{"index": q["index"], "source_id": q["candidate"]["source_id"],
                    "field_path": q["candidate"]["path"], "supported": True, "visual_supported": False, "reason": "Exact row"} for q in request["questions"]]}
            result = []
            for w in request["evidence_windows"]:
                result.append({"field_id": fields[("records", None, "amount")], "source_id": w["id"],
                    "column": 1 if w["cells"] else None, "value": int(w["cells"][1]["raw"]) if w["cells"] else 42, "raw_value": "42", "quote": w["text"]})
                if (request.get("targeted_retry") or {}).get("identity_path"):
                    result.append({"field_id": fields[("records", None, "code")], "source_id": w["id"],
                        "column": 0, "value": "Q", "raw_value": "bad copied identifier", "quote": "bad quote"})
            return {"candidates": result}
    outcome = GroundedExtractionPipeline(Model()).run(doc, schema)
    assert outcome.data == {"records": [{"code": "Q", "amount": None if conflict else 42}]}
    assert any(d["rejectionReason"] == "unresolved_unique_entity_identity" for d in outcome.debug)
    assert all(p["identitySchemaEvidence"] for p in outcome.provenance)


def test_exactly_printed_identifier_cannot_change_case():
    window = row(label="Ab1")
    decision = prevalidate(candidate(["code"], "AB1", "Ab1", quote=window.text, column=0),
        {window.id: window}, {window.id: window.parent_id}, contract({"code": {
            "type": "string", "description": "Identifier exactly as printed."}}))
    assert not decision.accepted and decision.reason == "source_spelling_required"

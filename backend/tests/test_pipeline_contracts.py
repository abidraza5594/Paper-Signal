import json

import pytest

from app.extraction.building import build_json, resolve_conflicts
from app.extraction.entity_resolution import resolve_identities
from app.extraction.llm import response_schema
from app.extraction.schema import analyze, at_path, is_valid
from app.extraction.types import Candidate, Decision
from app.schema_service import validator


def test_provider_contract_uses_field_ids_instead_of_model_generated_paths():
    schema = {"type": "object", "properties": {"amount": {"type": "number"}}}
    prompt = json.dumps({"extraction_plan": analyze(schema), "evidence_windows": [{"id": "p1:b0"}]})
    output_schema = response_schema(prompt)
    assert output_schema["properties"]["candidates"]["items"]["properties"]["field_id"]["enum"] == ["f0", "f1"]
    assert not validator(output_schema).is_valid({"candidates": [{"field_id": "made_up"}]})


def test_verdict_schema_cannot_answer_child_field_instead_of_requested_parent():
    schema = response_schema(json.dumps({"questions": [{"index": 0, "source_id": "p1:b0",
                                                       "candidate": {"path": ["record", "location"]}}]}))
    verdict = {"index": 0, "source_id": "p1:b0", "field_path": ["record", "location", "country"],
               "supported": True, "visual_supported": True, "reason": "Wrong question"}
    assert not validator(schema).is_valid({"verdicts": [verdict]})
    verdict["field_path"] = ["record", "location"]
    assert validator(schema).is_valid({"verdicts": [verdict]})


def test_recursive_local_schema_has_bounded_plan_and_valid_leaf_paths():
    schema = {"type": "object", "properties": {"value": {"type": "number"}, "next": {"$ref": "#"}}, "additionalProperties": False}
    assert len(analyze(schema)) < 20
    assert is_valid(42, at_path(schema, ["next", "next", "value"]), schema)


def test_schema_driven_dynamic_keys_are_planned_and_validated():
    schema = {"type": "object", "additionalProperties": {"type": "number"}}
    fields = [f for f in analyze(schema) if f.get("dynamic_key_positions")]
    assert len(fields) == 1 and fields[0]["dynamic_key_positions"] == [0]
    assert is_valid(3, at_path(schema, ["arbitrary key"]), schema)
    assert not is_valid("three", at_path(schema, ["arbitrary key"]), schema)


def entity_candidate(entity, name, value):
    return Decision(Candidate(path=["records", None, name], entity_ids=[entity], source_id=entity,
                              raw_value=str(value), value=value, quote=str(value)), True, "accepted", .95)


def test_strong_identifiers_merge_repeats_and_detect_conflicts():
    schema = {"type": "object", "properties": {"records": {"type": "array", "items": {
        "type": "object", "properties": {
            "key": {"type": "string", "x-extraction": {"identity": True}},
            "measurement": {"type": ["number", "null"]}}, "additionalProperties": False}}}, "additionalProperties": False}
    decisions = [entity_candidate("a", "key", "Q7"), entity_candidate("b", "key", "Q7"),
                 entity_candidate("a", "measurement", 3), entity_candidate("b", "measurement", 4)]
    resolve_identities(decisions, schema)
    resolve_conflicts(decisions)
    data, errors = build_json(schema, decisions)
    assert not errors
    assert data == {"records": [{"key": "Q7", "measurement": None}]}
    assert [d.reason for d in decisions[2:]] == ["unresolved_conflict", "unresolved_conflict"]


def test_unmarked_repeated_labels_never_merge_entities():
    schema = {"type": "object", "properties": {"records": {"type": "array", "items": {
        "type": "object", "properties": {"key": {"type": "string"}}}}}}
    decisions = [entity_candidate("a", "key", "same"), entity_candidate("b", "key", "same")]
    resolve_identities(decisions, schema)
    data, errors = build_json(schema, decisions)
    assert not errors
    assert data == {"records": [{"key": "same"}, {"key": "same"}]}


@pytest.mark.parametrize("constraint", [{"uniqueItems": True}, {"description": "Unique tags explicitly listed."}])
def test_explicit_unique_primitive_arrays_keep_one_value_and_all_citations(constraint):
    schema = {"type": "object", "properties": {"tags": {"type": "array", "items": {"type": "string"}, **constraint}}}
    decisions = [Decision(Candidate(path=["tags", None], entity_ids=[entity], source_id=entity,
        raw_value="same", value="same", quote="same"), True, "accepted", .95) for entity in ("a", "b")]
    resolve_identities(decisions, schema)
    data, errors = build_json(schema, decisions)
    assert not errors and data == {"tags": ["same"]}
    assert [d.field_path for d in decisions] == ["/tags/0", "/tags/0"]


def test_conflict_withholds_related_interpretations_of_the_same_cell():
    def fact(source, name, value, column):
        d = entity_candidate(source, name, value)
        d.candidate.column = column
        d.resolved_entity_ids = ("same-entity",)
        return d
    decisions = [fact("a", "category", "Regular", 1), fact("b", "category", "Premier", 1),
                 fact("a", "count", 2, 1), fact("a", "measurement", 1135, 2)]
    resolve_conflicts(decisions)
    assert [d.accepted for d in decisions] == [False, False, False, True]
    assert decisions[2].reason == "ambiguous_shared_cell_evidence"

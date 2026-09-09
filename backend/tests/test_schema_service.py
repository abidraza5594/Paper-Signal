import json
import pytest

from app.schema_service import OutputSchemaError, UnsatisfiedContractError, exact_shape, parse_json_schema_contract, parse_output_contract


def test_contract_is_not_rewritten():
    schema = {"type": "object", "properties": {
        "optional": {"type": "string", "pattern": "^[A-Z]+$"},
        "nested": {"type": ["object", "null"], "additionalProperties": {"type": "number"}}},
        "required": ["nested"], "additionalProperties": False}
    result = parse_json_schema_contract(json.dumps(schema))
    assert result.schema == schema
    assert exact_shape({"nested": None}, result.schema) == {"nested": None}
    with pytest.raises(UnsatisfiedContractError):
        exact_shape({"optional": None, "nested": None}, result.schema)


def test_missing_required_field_cannot_be_repaired_with_a_guess():
    schema = {"type": "object", "required": ["answer"], "properties": {"answer": {"type": "number"}}}
    with pytest.raises(UnsatisfiedContractError):
        exact_shape({}, schema)


@pytest.mark.parametrize("raw", ['{"name":"string"}', '{bad-json}', '[]'])
def test_api_rejects_non_schema_inputs(raw):
    with pytest.raises(OutputSchemaError):
        parse_json_schema_contract(raw)


def test_local_references_and_composition_are_supported():
    schema = {"$defs": {"code": {"type": "string", "pattern": "^[A-Z]+$"}},
              "type": "object", "properties": {"code": {"$ref": "#/$defs/code"}},
              "additionalProperties": False}
    result = parse_json_schema_contract(json.dumps(schema))
    assert exact_shape({"code": "OK"}, result.schema) == {"code": "OK"}
    with pytest.raises(UnsatisfiedContractError):
        exact_shape({"code": "bad"}, result.schema)


@pytest.mark.parametrize("ref", ["https://example.com/schema", "file:///private.json"])
def test_external_references_cannot_fetch_data(ref):
    with pytest.raises(OutputSchemaError, match="bundled"):
        parse_json_schema_contract(json.dumps({"$ref": ref}))


def test_legacy_examples_are_separate_from_api_contracts():
    assert parse_output_contract('{"name":""}').mode == "example"
    with pytest.raises(OutputSchemaError):
        parse_json_schema_contract('{"name":""}')


@pytest.mark.parametrize("schema", [{"minimum": 3}, {"pattern": "^[A-Z]+$"},
    {"items": {"type": "number"}}, {"required": ["code"]}, {"description": "Printed identifier"}])
def test_valid_constraint_only_schemas_are_preserved(schema):
    assert parse_json_schema_contract(json.dumps(schema)).schema == schema

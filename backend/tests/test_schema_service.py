import json

import pytest

from app.schema_service import (
    OutputSchemaError,
    exact_shape,
    extraction_response_schema,
    parse_json_schema_contract,
    parse_output_contract,
)


SCHEMA = {
    "type": "object",
    "properties": {
        "Date of Birth": {"type": "string"},
        "Father's name": {"type": "string"},
        "Occupation": {"type": "string"},
        "Birthplace": {"type": "string"},
        "education": {
            "type": "object",
            "properties": {
                "degree": {"type": "string"},
                "year of graduation": {"type": "string"},
            },
        },
    },
}


def test_json_schema_is_nullable_required_and_exact():
    contract = parse_output_contract(json.dumps(SCHEMA))
    assert contract is not None
    assert contract.mode == "json_schema"

    shaped = exact_shape(
        {
            "Occupation": "Developer",
            "education": {"degree": "BCA", "extra": "ignored"},
            "unexpected": "ignored",
        },
        contract.schema,
    )

    assert shaped == {
        "Date of Birth": None,
        "Father's name": None,
        "Occupation": "Developer",
        "Birthplace": None,
        "education": {"degree": "BCA", "year of graduation": None},
    }
    assert contract.schema["additionalProperties"] is False
    assert set(contract.schema["required"]) == set(SCHEMA["properties"])


def test_example_json_creates_the_same_fixed_shape():
    contract = parse_output_contract('{"name":"","skills":[],"education":{"degree":""}}')
    assert contract is not None
    assert contract.mode == "example"
    assert exact_shape({}, contract.schema) == {
        "name": None,
        "skills": None,
        "education": {"degree": None},
    }


def test_mistral_response_schema_wraps_user_data_contract():
    contract = parse_output_contract(json.dumps(SCHEMA))
    wrapper = extraction_response_schema(contract.schema)
    assert wrapper["properties"]["data"] == contract.schema
    assert wrapper["additionalProperties"] is False


def test_required_schema_parser_rejects_example_objects():
    with pytest.raises(OutputSchemaError, match="JSON Schema"):
        parse_json_schema_contract('{"name":"string"}')


def test_objects_are_never_nullable_so_the_model_cannot_skip_a_whole_branch():
    """A nullable object lets the model answer `null` for an entire branch.

    A 41-page brochure came back with every field null while the text was
    plainly in the document: the model had answered `"data": null`, which the
    contract allowed, and `exact_shape` expanded that into a full null tree.
    Objects stay non-nullable so the only legal answer is a real object.
    """
    nullable_objects = {
        "type": "object",
        "properties": {
            "basics": {
                "type": ["object", "null"],
                "properties": {
                    "projectName": {"type": ["string", "null"]},
                    "address": {
                        "type": ["object", "null"],
                        "properties": {"city": {"type": ["string", "null"]}},
                    },
                },
            }
        },
    }
    contract = parse_json_schema_contract(json.dumps(nullable_objects))

    assert "null" not in contract.schema["type"]
    assert "null" not in contract.schema["properties"]["basics"]["type"]
    assert "null" not in contract.schema["properties"]["basics"]["properties"]["address"]["type"]

    # Leaves stay nullable: a field that is genuinely absent must still be null.
    leaf = contract.schema["properties"]["basics"]["properties"]["projectName"]
    assert "null" in leaf["type"]


def test_example_json_also_produces_non_nullable_objects():
    contract = parse_output_contract('{"education":{"degree":""}}')
    assert contract is not None
    assert "null" not in contract.schema["type"]
    assert "null" not in contract.schema["properties"]["education"]["type"]

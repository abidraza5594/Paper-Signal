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

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any


class OutputSchemaError(ValueError):
    pass


@dataclass(frozen=True)
class OutputContract:
    schema: dict[str, Any]
    mode: str


SUPPORTED_TYPES = {"object", "array", "string", "number", "integer", "boolean", "null"}


def parse_output_contract(raw: str | None) -> OutputContract | None:
    if not raw or not raw.strip():
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OutputSchemaError(
            f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}."
        ) from exc
    if not isinstance(value, dict):
        raise OutputSchemaError("Output JSON must be an object at the top level.")

    is_schema = value.get("type") == "object" and isinstance(value.get("properties"), dict)
    schema = _normalize_schema(value, depth=0) if is_schema else _schema_from_example(value, depth=0)
    return OutputContract(schema=schema, mode="json_schema" if is_schema else "example")


def parse_json_schema_contract(raw: str | None) -> OutputContract:
    """Parse the required user input and reject example objects or missing schemas."""
    contract = parse_output_contract(raw)
    if contract is None or contract.mode != "json_schema":
        raise OutputSchemaError(
            'Input must be a JSON Schema with root type "object" and a non-empty '
            '"properties" object.'
        )
    return contract


def _nullable_type(value: object) -> list[str]:
    if isinstance(value, str):
        types = [value]
    elif isinstance(value, list) and all(isinstance(item, str) for item in value):
        types = list(value)
    else:
        raise OutputSchemaError("Every schema field must define a supported JSON type.")
    if any(item not in SUPPORTED_TYPES for item in types):
        raise OutputSchemaError("Schema contains an unsupported JSON type.")
    return [*types, "null"] if "null" not in types else types


def _normalize_schema(schema: dict[str, Any], depth: int) -> dict[str, Any]:
    if depth > 8:
        raise OutputSchemaError("Schema nesting cannot exceed 8 levels.")
    if any(key in schema for key in ("$ref", "allOf", "anyOf", "oneOf", "not")):
        raise OutputSchemaError("$ref and schema composition keywords are not supported.")

    types = _nullable_type(schema.get("type"))
    primary_type = next((item for item in types if item != "null"), "null")
    normalized: dict[str, Any] = {"type": types}
    for key in ("description", "enum", "format", "minimum", "maximum", "minLength", "maxLength"):
        if key in schema:
            normalized[key] = copy.deepcopy(schema[key])

    if primary_type == "object":
        properties = schema.get("properties")
        if not isinstance(properties, dict) or not properties:
            raise OutputSchemaError("Every object schema must contain at least one property.")
        if len(properties) > 100:
            raise OutputSchemaError("A schema object cannot contain more than 100 properties.")
        normalized["properties"] = {
            str(name): _normalize_schema(child, depth + 1)
            for name, child in properties.items()
            if isinstance(child, dict)
        }
        if len(normalized["properties"]) != len(properties):
            raise OutputSchemaError("Every property definition must be a JSON object.")
        normalized["required"] = list(normalized["properties"].keys())
        normalized["additionalProperties"] = False
    elif primary_type == "array":
        items = schema.get("items", {"type": "string"})
        if not isinstance(items, dict):
            raise OutputSchemaError("Array items must contain a valid schema object.")
        normalized["items"] = _normalize_schema(items, depth + 1)
    return normalized


def _schema_from_example(value: Any, depth: int) -> dict[str, Any]:
    if depth > 8:
        raise OutputSchemaError("JSON nesting cannot exceed 8 levels.")
    if isinstance(value, dict):
        if not value:
            raise OutputSchemaError("Example JSON must contain at least one field.")
        properties = {str(key): _schema_from_example(item, depth + 1) for key, item in value.items()}
        return {
            "type": ["object", "null"],
            "properties": properties,
            "required": list(properties.keys()),
            "additionalProperties": False,
        }
    if isinstance(value, list):
        item_schema = _schema_from_example(value[0], depth + 1) if value else {"type": ["string", "null"]}
        return {"type": ["array", "null"], "items": item_schema}
    if isinstance(value, bool):
        return {"type": ["boolean", "null"]}
    if isinstance(value, int):
        return {"type": ["integer", "null"]}
    if isinstance(value, float):
        return {"type": ["number", "null"]}
    return {"type": ["string", "null"]}


def exact_shape(value: Any, schema: dict[str, Any]) -> Any:
    types = schema.get("type", [])
    if isinstance(types, str):
        types = [types]
    primary_type = next((item for item in types if item != "null"), "null")

    if primary_type == "object":
        source = value if isinstance(value, dict) else {}
        return {
            name: exact_shape(source.get(name), child)
            for name, child in schema.get("properties", {}).items()
        }
    if value is None:
        return None
    if primary_type == "array":
        if not isinstance(value, list):
            return None
        return [exact_shape(item, schema.get("items", {"type": ["string", "null"]})) for item in value]
    if primary_type == "string":
        return value if isinstance(value, str) else None
    if primary_type == "boolean":
        return value if isinstance(value, bool) else None
    if primary_type == "integer":
        return value if isinstance(value, int) and not isinstance(value, bool) else None
    if primary_type == "number":
        return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None
    return None


def extraction_response_schema(data_schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "data": data_schema,
            "evidence": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "page": {"type": ["integer", "null"]},
                        "evidence": {"type": "string"},
                    },
                    "required": ["label", "page", "evidence"],
                    "additionalProperties": False,
                },
            },
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["data", "evidence", "warnings"],
        "additionalProperties": False,
    }

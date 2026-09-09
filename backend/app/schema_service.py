"""User contracts are immutable; missing data never changes their meaning."""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any

from jsonschema import FormatChecker
from jsonschema.validators import Draft4Validator, Draft6Validator, Draft7Validator, Draft201909Validator, Draft202012Validator, validator_for
from referencing import Registry


class OutputSchemaError(ValueError):
    pass


SCHEMA_KEYWORDS = set().union(*(v.VALIDATORS for v in (
    Draft4Validator, Draft6Validator, Draft7Validator, Draft201909Validator, Draft202012Validator,
))) | {"$schema", "$id", "id", "$defs", "definitions", "$anchor", "$dynamicAnchor",
      "$comment", "title", "description", "default", "examples", "readOnly", "writeOnly", "deprecated"}


class UnsatisfiedContractError(OutputSchemaError):
    def __init__(self, paths: list[str], partial: Any):
        super().__init__("Source evidence cannot satisfy the JSON Schema at: " + ", ".join(paths))
        self.paths = paths
        self.partial = partial


@dataclass(frozen=True)
class OutputContract:
    schema: dict[str, Any] | bool
    mode: str


def validator(schema: Any):
    # An empty registry prevents network/file resolution of untrusted refs.
    return validator_for(schema)(schema, format_checker=FormatChecker(), registry=Registry())


def check_schema(schema: Any) -> None:
    try:
        validator_for(schema).check_schema(schema)
        def walk(node: Any) -> None:
            if isinstance(node, dict):
                if "$schema" in node and node["$schema"] not in (
                    "https://json-schema.org/draft/2020-12/schema",
                    "https://json-schema.org/draft/2019-09/schema",
                    "http://json-schema.org/draft-07/schema#",
                    "http://json-schema.org/draft-06/schema#",
                    "http://json-schema.org/draft-04/schema#",
                ):
                    raise OutputSchemaError("Unsupported JSON Schema dialect.")
                for key in ("$ref", "$dynamicRef", "$recursiveRef"):
                    if key in node and not node[key].startswith("#"):
                        raise OutputSchemaError("References must be bundled within the supplied schema.")
                for child in node.values():
                    walk(child)
            elif isinstance(node, list):
                for child in node:
                    walk(child)
        walk(schema)
    except OutputSchemaError:
        raise
    except Exception as exc:
        raise OutputSchemaError("Invalid JSON Schema.") from exc


def parse_json_schema_contract(raw: str | None) -> OutputContract:
    try:
        schema = json.loads(raw or "", parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, TypeError) as exc:
        raise OutputSchemaError("Invalid JSON. Input must be a JSON Schema.") from exc
    if not isinstance(schema, (dict, bool)) or (isinstance(schema, dict) and schema and not any(
        key in SCHEMA_KEYWORDS for key in schema
    )):
        raise OutputSchemaError("Input must be a JSON Schema, not an example object.")
    check_schema(schema)
    return OutputContract(copy.deepcopy(schema), "json_schema")


def parse_output_contract(raw: str | None) -> OutputContract | None:
    if not raw or not raw.strip():
        return None
    try:
        return parse_json_schema_contract(raw)
    except OutputSchemaError:
        value = json.loads(raw)
        if isinstance(value, dict) and not any(k in value for k in ("type", "$schema", "$ref", "properties")):
            return OutputContract(_schema_from_example(value), "example")
        raise


def _schema_from_example(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {"type": "object", "properties": {k: _schema_from_example(v) for k, v in value.items()},
                "required": list(value), "additionalProperties": False}
    if isinstance(value, list):
        return {"type": ["array", "null"], "items": _schema_from_example(value[0]) if value else {"type": "string"}}
    kind = "boolean" if isinstance(value, bool) else "integer" if isinstance(value, int) else "number" if isinstance(value, float) else "string"
    return {"type": [kind, "null"]}


def exact_shape(value: Any, schema: Any) -> Any:
    """Compatibility API: validate, never coerce or discard constraints."""
    errors = list(validator(schema).iter_errors(value))
    if errors:
        raise UnsatisfiedContractError(sorted({"/" + "/".join(map(str, e.absolute_path)) for e in errors}), value)
    return value


def extraction_response_schema(data_schema: Any) -> dict[str, Any]:
    return {"type": "object", "properties": {
        "data": data_schema,
        "evidence": {"type": "array", "items": {"type": "object", "properties": {
            "label": {"type": "string"}, "page": {"type": ["integer", "null"]}, "evidence": {"type": "string"}},
            "required": ["label", "page", "evidence"], "additionalProperties": False}},
        "warnings": {"type": "array", "items": {"type": "string"}}},
        "required": ["data", "evidence", "warnings"], "additionalProperties": False}

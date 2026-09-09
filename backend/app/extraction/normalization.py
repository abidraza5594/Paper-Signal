"""Only reproducible, schema-authorized conversions can support a changed value."""
from __future__ import annotations

import json
import math
import re
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any


def supported_value(raw: str, value: Any, policy: dict[str, Any]) -> tuple[bool, str]:
    if isinstance(value, (list, dict)) or value is None:
        return False, "non_scalar_candidate"
    if isinstance(value, str) and raw == value:
        return True, "none"
    if isinstance(value, str) and " ".join(unicodedata.normalize("NFKC", raw).split()) == value:
        return True, "text_encoding_and_whitespace"
    if isinstance(value, str) and value and re.search(r"(?<!\w)" + re.escape(value) + r"(?!\w)", raw):
        return True, "exact_text_component"
    if isinstance(value, str) and raw.casefold() == value.casefold():
        return True, "case_normalization"
    mapping = policy.get("valueMap")
    if isinstance(mapping, dict) and raw in mapping and type(mapping[raw]) is type(value) and mapping[raw] == value:
        return True, "schema_value_map"
    if isinstance(value, bool):
        description = policy.get("description", "").lower()
        if re.search(r"\b" + str(value).lower() + r"\b.{0,30}\b(if|when|only)\b", description):
            # This requires the later semantic (and, for scans, visual) verifier.
            return True, "description_boolean_condition"
        return (raw in ("true", "false") and (raw == "true") == value), "boolean_literal"
    if isinstance(value, (float, int)) and not isinstance(value, bool):
        if not math.isfinite(value):
            return False, "non_finite_number"
        text = raw.strip()
        operation = "numeric_literal"
        description = policy.get("description", "")
        if re.search(r"\b(numeric value only|number only|number of)\b", description, re.I):
            numbers = re.findall(r"[+-]?\d[\d,.]*(?:[eE][+-]?\d+)?", text)
            if len(numbers) == 1:
                text = numbers[0]
                operation = "description_numeric_component"
        if re.fullmatch(r"\d+(st|nd|rd|th)", text, re.I):
            text = re.sub(r"(st|nd|rd|th)$", "", text, flags=re.I)
            operation = "printed_numeric_ordinal"
        if re.search(r"\b(first|last) numeric\b", description, re.I):
            numbers = re.findall(r"\d+", text)
            if 1 <= len(numbers) <= 2:
                text = numbers[-1] if re.search(r"\blast numeric\b", description, re.I) else numbers[0]
                operation = "description_range_endpoint"
        grouping = policy.get("thousandsSeparator")
        decimal = policy.get("decimalSeparator", ".")
        if grouping and grouping != decimal:
            pattern = rf"[+-]?\d{{1,3}}(?:{re.escape(grouping)}\d{{3}})+(?:{re.escape(decimal)}\d+)?"
            if grouping in text:
                if not re.fullmatch(pattern, text):
                    return False, "ambiguous_number_grouping"
                text = text.replace(grouping, "")
                operation = "schema_numeric_format"
        if decimal != ".":
            text = text.replace(decimal, ".")
            operation = "schema_numeric_format"
        if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?", text):
            return False, "ambiguous_number_or_unit"
        try:
            numeric = Decimal(text)
            if policy.get("scale") is not None:
                numeric *= Decimal(str(policy["scale"]))
                operation = "schema_scale"
            return numeric == Decimal(str(value)), operation
        except (InvalidOperation, ValueError):
            return False, "ambiguous_number"
    if isinstance(value, str) and policy.get("dateFormat"):
        try:
            expected = datetime.strptime(raw, policy["dateFormat"]).date().isoformat()
            return expected == value, "schema_date_format"
        except (ValueError, TypeError):
            return False, "ambiguous_date"
    description = policy.get("description", "")
    if isinstance(value, str) and re.search(r"\b(ISO|yyyy-MM-dd)\b", description, re.I):
        if re.search(r"\b(partial dates|quarter)\b", description, re.I):
            match = re.fullmatch(r"Q([1-4])\s+(\d{4})", raw, re.I)
            if match:
                return value == f"{match[2]}-{(int(match[1])-1)*3+1:02d}-01", "description_quarter_start"
        for date_format in ("%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y", "%d-%b-%Y"):
            try:
                if datetime.strptime(raw, date_format).date().isoformat() == value:
                    return True, "description_iso_date"
            except ValueError:
                continue
    # Explicit symbolic mappings in arbitrary descriptions; no built-in domain maps.
    if isinstance(value, str):
        for source, target in re.findall(r"([\w /.-]+?)\s*(?:=>|->|→)\s*([\w.-]+)", description):
            if source.strip().strip("'\"") == raw and target.strip().strip("'\"") == value:
                return True, "description_explicit_map"
    # Free-form instructions still go to the semantic verifier, but cannot authorize
    # an unimplemented conversion. Abstain instead of executing model-proposed code.
    return False, "unsupported_or_ambiguous_normalization"

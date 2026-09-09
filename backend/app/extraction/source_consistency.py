"""Withhold unique-entity facts when homologous printed cells disagree.

This gate never admits a value or overrides a verifier rejection. It checks
native rows even when the model omitted/rejected a candidate for that row.
"""
from __future__ import annotations

import re
import unicodedata

from .normalization import supported_value
from .schema import at_path, instructions


def _header(value: str) -> str:
    return re.sub(r"[\W_]", "", unicodedata.normalize("NFKC", value).casefold())


def _column_heading(window, column):
    heading = window.columns[column] if column < len(window.columns) else ""
    if heading or len(window.table_context) < 2:
        return _header(heading)
    # Native extraction may designate a merged title as the first header.
    # Consider its immediately following fully textual subheader only; never
    # scan arbitrary data rows for labels or infer labels from field names.
    subheader = window.table_context[1]
    populated = [v for v in subheader if isinstance(v, str) and v.strip()]
    if (len(subheader) == len(window.columns) and len(populated) == len(subheader)
            and all(re.search(r"[^\W\d_]", v) and not re.search(r"\d", v) for v in populated)):
        return _header(subheader[column])
    return ""


def withhold_source_disagreements(decisions, windows, schema, identity_paths=()) -> None:
    for identity_path in identity_paths:
        # Deeper parents need independently established cross-page ancestry.
        if identity_path.count(None) != 1 or identity_path[-2] is not None:
            continue
        prefix = identity_path[:-1]
        identities = [d for d in decisions if d.accepted and d.candidate.path == identity_path]
        row_keys = {d.candidate.source_id: d.candidate.value for d in identities}
        table_keys = {}
        for decision in identities:
            c = decision.candidate
            window = windows[c.source_id]
            if window.table_id and c.column is not None and c.column < len(window.columns):
                table_keys.setdefault(window.table_id, set()).add(c.column)
        related_rows = {}
        for window in windows.values():
            columns = table_keys.get(window.table_id, set())
            if len(columns) != 1:
                continue
            column = next(iter(columns))
            if column < len(window.cells):
                key = window.cells[column].raw
                if key in row_keys.values():
                    related_rows.setdefault(key, []).append(window)
        for decision in decisions:
            c = decision.candidate
            if not decision.accepted or c.path[:-1] != prefix or c.path == identity_path or c.column is None:
                continue
            key = row_keys.get(c.source_id)
            source = windows[c.source_id]
            if key is None or c.column >= len(source.columns):
                continue
            heading = _column_heading(source, c.column)
            if not heading:
                continue
            policy = instructions(at_path(schema, c.path), schema)
            conflicts = []
            for other in related_rows.get(key, []):
                if other.id == source.id:
                    continue
                matches = [i for i in range(len(other.columns)) if _column_heading(other, i) == heading]
                if len(matches) != 1 or matches[0] >= len(other.cells):
                    continue
                column = matches[0]
                raw = other.cells[column].raw
                if not raw or not raw.strip() or raw == c.raw_value:
                    continue
                supported, _ = supported_value(raw, c.value, policy)
                if not supported:
                    conflicts.append({"source_id": other.id, "column": column, "raw_value": raw})
            if conflicts:
                decision.accepted = False
                decision.confidence = 0
                decision.reason = "unresolved_repeated_source_value"
                decision.verification["source_consistency_conflicts"] = conflicts

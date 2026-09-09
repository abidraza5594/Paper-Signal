"""Rank local windows but cover every window; retrieval rank never proves absence."""
import re
from typing import Any
from .types import EvidenceWindow


def evidence_mapping(plan: list[dict[str, Any]], windows: list[EvidenceWindow]) -> dict[str, list[list[str | None]]]:
    mapping = {w.id: [] for w in windows}
    for field in plan:
        text = " ".join(str(t) for t in field["path"] if t is not None) + " " + field.get("instructions", {}).get("description", "")
        terms = set(re.findall(r"\w+", text.casefold()))
        ranked = sorted(windows, key=lambda w: -len(terms & set(re.findall(r"\w+", " ".join([w.text, w.section, *w.columns]).casefold()))))
        for window in ranked:
            if terms & set(re.findall(r"\w+", " ".join([window.text, window.section, *window.columns]).casefold())):
                mapping[window.id].append(field["path"])
    return mapping

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, model_validator


@dataclass(frozen=True)
class Cell:
    column: int
    raw: str | None
    bbox: tuple[float, ...] | None = None
    merged_with: str | None = None


@dataclass(frozen=True)
class Table:
    id: str
    page: int
    bbox: tuple[float, ...] | None
    heading: str
    columns: list[str]
    rows: list[list[Cell]]
    parent_id: str
    nearby_text: str = ""


@dataclass(frozen=True)
class EvidenceWindow:
    id: str
    page: int
    text: str
    entity_id: str
    parent_id: str
    section: str = ""
    table_id: str | None = None
    row_id: str | None = None
    bbox: tuple[float, ...] | None = None
    cells: list[Cell] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    parser: str = "text"
    quality: float = 1.0
    visual_required: bool = False
    table_context: list[list[str | None]] = field(default_factory=list)

    def payload(self) -> dict[str, Any]:
        return asdict(self)


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Pointer tokens; null is an array entity placeholder, distinct from property '*'.
    path: list[StrictStr | None]
    entity_ids: list[StrictStr] = Field(default_factory=list)
    source_id: StrictStr
    raw_value: StrictStr = Field(min_length=1, max_length=4000)
    value: Any
    quote: StrictStr = Field(min_length=1, max_length=8000)
    label: StrictStr = ""
    column: StrictInt | None = None
    evidence_binding: StrictStr = "model_quote"

    @model_validator(mode="before")
    @classmethod
    def scalar_identity_is_source_identity(cls, value):
        # Scalar paths have no array entity slots. Ignore extraneous model IDs;
        # source_id still pins the value to its server-owned source entity.
        if isinstance(value, dict) and isinstance(value.get("path"), list) and None not in value["path"]:
            return {**value, "entity_ids": []}
        return value


@dataclass
class Decision:
    candidate: Candidate
    accepted: bool
    reason: str
    confidence: float = 0.0
    normalization: str = "none"
    field_path: str | None = None
    resolved_entity_ids: tuple[str, ...] | None = None
    verification: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionOutcome:
    data: Any
    provenance: list[dict[str, Any]]
    debug: list[dict[str, Any]]
    warnings: list[str]
    schema_valid: bool
    validation_paths: list[str] = field(default_factory=list)

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class OcrMode(str, Enum):
    auto = "auto"
    always = "always"
    never = "never"


class EvidenceItem(BaseModel):
    label: str = Field(default="Finding", max_length=300)
    page: int | None = Field(default=None, ge=1)
    evidence: str = Field(default="", max_length=2000)


class PartialExtraction(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_empty_ai_values(cls, value: Any) -> Any:
        """Normalize harmless nulls commonly returned by structured-output models."""
        if not isinstance(value, dict):
            return value

        normalized = dict(value)
        if normalized.get("data") is None:
            normalized["data"] = {}
        if normalized.get("evidence") is None:
            normalized["evidence"] = []
        elif isinstance(normalized.get("evidence"), list):
            evidence_items: list[Any] = []
            for item in normalized["evidence"]:
                if isinstance(item, dict):
                    if item.get("evidence") is None:
                        continue
                    if item.get("label") is None:
                        item = {**item, "label": "Finding"}
                evidence_items.append(item)
            normalized["evidence"] = evidence_items
        if normalized.get("warnings") is None:
            normalized["warnings"] = []
        elif isinstance(normalized.get("warnings"), list):
            normalized["warnings"] = [
                warning for warning in normalized["warnings"] if warning is not None
            ]
        return normalized


class ExtractionResult(PartialExtraction):
    request: str
    document: dict[str, Any]


class JobRecord(BaseModel):
    id: str
    batch_id: str | None = None
    file_name: str
    file_path: str
    file_size: int
    instruction: str
    output_template: str | None = None
    ocr_mode: OcrMode = OcrMode.auto
    status: JobStatus = JobStatus.queued
    progress: int = Field(default=0, ge=0, le=100)
    stage: str = "Queued"
    error: str | None = None
    result: dict[str, Any] | None = None
    page_count: int | None = None
    ocr_pages: int = 0
    python_text_pages: int = 0
    vision_attempted_pages: int = 0
    vision_pages: int = 0
    vision_failed_pages: int = 0
    text_model: str | None = None
    vision_model: str | None = None
    ocr_model: str | None = None
    schema_mode: str = "none"
    duration_ms: int | None = None
    failure_code: str | None = None
    failure_stage: str | None = None
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


class JobPublic(BaseModel):
    id: str
    batch_id: str | None
    file_name: str
    file_size: int
    instruction: str
    ocr_mode: OcrMode
    status: JobStatus
    progress: int
    stage: str
    error: str | None
    result: dict[str, Any] | None
    page_count: int | None
    ocr_pages: int
    python_text_pages: int
    vision_attempted_pages: int
    vision_pages: int
    vision_failed_pages: int
    text_model: str | None
    vision_model: str | None
    ocr_model: str | None
    schema_mode: str
    output_template: str | None
    duration_ms: int | None
    failure_code: str | None
    failure_stage: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_record(cls, record: JobRecord) -> "JobPublic":
        return cls(**record.model_dump(exclude={"file_path"}))


class BatchFileRejection(BaseModel):
    file_name: str
    error: str


class BatchJobResponse(BaseModel):
    batch_id: str
    jobs: list[JobPublic] = Field(default_factory=list)
    rejected: list[BatchFileRejection] = Field(default_factory=list)
    accepted_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)


class HealthResponse(BaseModel):
    status: str = "ok"
    ai_configured: bool
    max_upload_mb: int
    max_pdf_pages: int
    max_batch_files: int
    max_batch_total_mb: int
    text_model: str
    vision_model: str
    ocr_model: str

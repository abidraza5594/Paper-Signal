from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from .models import JobRecord, utc_now_iso


class JobDatabase:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.RLock()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    batch_id TEXT,
                    api_key_id TEXT,
                    file_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    instruction TEXT NOT NULL,
                    output_template TEXT,
                    ocr_mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress INTEGER NOT NULL,
                    stage TEXT NOT NULL,
                    error TEXT,
                    result_json TEXT,
                    page_count INTEGER,
                    ocr_pages INTEGER NOT NULL DEFAULT 0,
                    python_text_pages INTEGER NOT NULL DEFAULT 0,
                    vision_attempted_pages INTEGER NOT NULL DEFAULT 0,
                    vision_pages INTEGER NOT NULL DEFAULT 0,
                    vision_failed_pages INTEGER NOT NULL DEFAULT 0,
                    text_model TEXT,
                    vision_model TEXT,
                    ocr_model TEXT,
                    schema_mode TEXT NOT NULL DEFAULT 'none',
                    duration_ms INTEGER,
                    failure_code TEXT,
                    failure_stage TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            existing_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(jobs)").fetchall()
            }
            migrations = {
                "batch_id": "TEXT",
                "api_key_id": "TEXT",
                "python_text_pages": "INTEGER NOT NULL DEFAULT 0",
                "vision_attempted_pages": "INTEGER NOT NULL DEFAULT 0",
                "vision_pages": "INTEGER NOT NULL DEFAULT 0",
                "vision_failed_pages": "INTEGER NOT NULL DEFAULT 0",
                "text_model": "TEXT",
                "vision_model": "TEXT",
                "ocr_model": "TEXT",
                "schema_mode": "TEXT NOT NULL DEFAULT 'none'",
                "duration_ms": "INTEGER",
                "failure_code": "TEXT",
                "failure_stage": "TEXT",
            }
            for column, definition in migrations.items():
                if column not in existing_columns:
                    connection.execute(f"ALTER TABLE jobs ADD COLUMN {column} {definition}")
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def create(self, job: JobRecord) -> JobRecord:
        data = job.model_dump(mode="json")
        data["result_json"] = json.dumps(data.pop("result")) if job.result is not None else None
        columns = [
            "id", "batch_id", "api_key_id", "file_name", "file_path", "file_size", "instruction", "output_template",
            "ocr_mode", "status", "progress", "stage", "error", "result_json",
            "page_count", "ocr_pages", "created_at", "updated_at"
            , "python_text_pages", "text_model", "ocr_model", "schema_mode",
            "duration_ms", "failure_code", "failure_stage", "vision_attempted_pages",
            "vision_pages", "vision_failed_pages", "vision_model"
        ]
        with self._lock, self._connect() as connection:
            connection.execute(
                f"INSERT INTO jobs ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                [data[column] for column in columns],
            )
            connection.commit()
        return job

    def get(self, job_id: str, api_key_id: str | None = None) -> JobRecord | None:
        query = "SELECT * FROM jobs WHERE id = ?"
        params: list[Any] = [job_id]
        if api_key_id is not None:
            query += " AND api_key_id = ?"
            params.append(api_key_id)
        with self._lock, self._connect() as connection:
            row = connection.execute(query, params).fetchone()
        return self._row_to_record(row) if row else None

    def list_recent(self, limit: int = 20, api_key_id: str | None = None) -> list[JobRecord]:
        query = "SELECT * FROM jobs"
        params: list[Any] = []
        if api_key_id is not None:
            query += " WHERE api_key_id = ?"
            params.append(api_key_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._lock, self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._row_to_record(row) for row in rows]

    def get_many(self, job_ids: list[str]) -> list[JobRecord]:
        if not job_ids:
            return []
        unique_ids = list(dict.fromkeys(job_ids))
        placeholders = ",".join("?" for _ in unique_ids)
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM jobs WHERE id IN ({placeholders})", unique_ids
            ).fetchall()
        records = {record.id: record for record in (self._row_to_record(row) for row in rows)}
        return [records[job_id] for job_id in unique_ids if job_id in records]

    def list_by_batch(self, batch_id: str, api_key_id: str | None = None) -> list[JobRecord]:
        query = "SELECT * FROM jobs WHERE batch_id = ?"
        params: list[Any] = [batch_id]
        if api_key_id is not None:
            query += " AND api_key_id = ?"
            params.append(api_key_id)
        query += " ORDER BY created_at ASC, id ASC"
        with self._lock, self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._row_to_record(row) for row in rows]

    def update(self, job_id: str, **changes: Any) -> JobRecord:
        if not changes:
            current = self.get(job_id)
            if current is None:
                raise KeyError(job_id)
            return current
        changes["updated_at"] = utc_now_iso()
        if "result" in changes:
            changes["result_json"] = json.dumps(changes.pop("result"), ensure_ascii=False)
        normalized = {
            key: value.value if hasattr(value, "value") else value for key, value in changes.items()
        }
        assignments = ", ".join(f"{key} = ?" for key in normalized)
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE jobs SET {assignments} WHERE id = ?",
                [*normalized.values(), job_id],
            )
            if cursor.rowcount == 0:
                raise KeyError(job_id)
            connection.commit()
        updated = self.get(job_id)
        if updated is None:
            raise KeyError(job_id)
        return updated

    def delete(self, job_id: str) -> bool:
        with self._lock, self._connect() as connection:
            cursor = connection.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            connection.commit()
            return cursor.rowcount > 0

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> JobRecord:
        data = dict(row)
        raw_result = data.pop("result_json")
        data["result"] = json.loads(raw_result) if raw_result else None
        return JobRecord.model_validate(data)

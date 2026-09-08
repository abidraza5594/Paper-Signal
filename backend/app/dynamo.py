"""DynamoDB versions of the job and API-key stores.

SQLite is a file on one machine's disk. A container platform replaces containers
without warning and can run several at once, so the data has to live outside them.

The access patterns are small and fixed, which is why DynamoDB fits:

  jobs        PK extraction_id, SK job_id   -> one query returns a whole extraction
  api_keys    PK key_hash                   -> one lookup per request
  usage       PK api_key_id, SK period      -> one atomic counter per key per month

Anything that needs a full table read (listing keys for the CLI) is rare and small.
"""

from __future__ import annotations

import threading
from decimal import Decimal
from typing import Any

from .api_keys import ApiKeyRecord, ApiKeyError, current_period, display_prefix, generate_key, hash_key
from .models import JobRecord, utc_now_iso


def _clean(value: Any) -> Any:
    """DynamoDB stores numbers as Decimal and rejects empty strings in keys."""
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, list):
        return [_clean(v) for v in value]
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    return value


def _to_item(data: dict) -> dict:
    """Floats are not valid DynamoDB numbers; nulls are stored as-is."""
    out = {}
    for key, value in data.items():
        if isinstance(value, float):
            out[key] = Decimal(str(value))
        elif isinstance(value, (dict, list)):
            out[key] = _floats_to_decimal(value)
        else:
            out[key] = value
    return out


def _floats_to_decimal(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, list):
        return [_floats_to_decimal(v) for v in value]
    if isinstance(value, dict):
        return {k: _floats_to_decimal(v) for k, v in value.items()}
    return value


class DynamoJobDatabase:
    """Same interface as JobDatabase, backed by one DynamoDB table."""

    #: jobs without an extraction (never produced by the current API) would be
    #: unqueryable, so every job is written under its extraction id.
    def __init__(self, table_name: str, resource=None):
        import boto3

        self.table = (resource or boto3.resource("dynamodb")).Table(table_name)

    def initialize(self) -> None:
        # The table is created by infrastructure, not by the application.
        return None

    def create(self, job: JobRecord) -> JobRecord:
        item = _to_item({k: v for k, v in job.model_dump(mode="json").items() if v is not None})
        item["extraction_id"] = job.batch_id or job.id
        item["job_id"] = job.id
        self.table.put_item(Item=item)
        return job

    def _record(self, item: dict) -> JobRecord:
        data = {k: _clean(v) for k, v in item.items() if k not in ("extraction_id", "job_id")}
        return JobRecord.model_validate(data)

    def get(self, job_id: str, api_key_id: str | None = None) -> JobRecord | None:
        found = self.table.query(
            IndexName="job_id-index",
            KeyConditionExpression="job_id = :j",
            ExpressionAttributeValues={":j": job_id},
            Limit=1,
        ).get("Items", [])
        if not found:
            return None
        record = self._record(found[0])
        if api_key_id is not None and record.api_key_id != api_key_id:
            return None
        return record

    def list_by_batch(self, batch_id: str, api_key_id: str | None = None) -> list[JobRecord]:
        items = self.table.query(
            KeyConditionExpression="extraction_id = :e",
            ExpressionAttributeValues={":e": batch_id},
        ).get("Items", [])
        records = [self._record(item) for item in items]
        if api_key_id is not None:
            records = [r for r in records if r.api_key_id == api_key_id]
        return sorted(records, key=lambda r: (r.created_at, r.id))

    def list_recent(self, limit: int = 20, api_key_id: str | None = None) -> list[JobRecord]:
        scan: dict[str, Any] = {"Limit": max(limit * 4, 40)}
        items = self.table.scan(**scan).get("Items", [])
        records = [self._record(item) for item in items]
        if api_key_id is not None:
            records = [r for r in records if r.api_key_id == api_key_id]
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records[:limit]

    def get_many(self, job_ids: list[str]) -> list[JobRecord]:
        unique = list(dict.fromkeys(job_ids))
        found = {}
        for job_id in unique:
            record = self.get(job_id)
            if record:
                found[job_id] = record
        return [found[j] for j in unique if j in found]

    def update(self, job_id: str, **changes: Any) -> JobRecord:
        current = self.get(job_id)
        if current is None:
            raise KeyError(job_id)
        changes["updated_at"] = utc_now_iso()
        normalized = {
            key: (value.value if hasattr(value, "value") else value)
            for key, value in changes.items()
        }
        merged = current.model_dump(mode="json")
        merged.update(normalized)
        updated = JobRecord.model_validate(merged)
        self.create(updated)
        return updated

    def delete(self, job_id: str) -> bool:
        record = self.get(job_id)
        if record is None:
            return False
        self.table.delete_item(
            Key={"extraction_id": record.batch_id or record.id, "job_id": record.id}
        )
        return True


class DynamoApiKeyStore:
    """Same interface as ApiKeyStore, backed by two DynamoDB tables."""

    def __init__(self, keys_table: str, usage_table: str, resource=None):
        import boto3

        dynamo = resource or boto3.resource("dynamodb")
        self.keys = dynamo.Table(keys_table)
        self.usage = dynamo.Table(usage_table)
        self._lock = threading.RLock()

    def initialize(self) -> None:
        return None

    @staticmethod
    def _record(item: dict) -> ApiKeyRecord:
        return ApiKeyRecord(
            id=item["id"],
            name=item["name"],
            key_prefix=item["key_prefix"],
            rate_limit_per_minute=int(item["rate_limit_per_minute"]),
            monthly_document_quota=int(item["monthly_document_quota"]),
            created_at=item["created_at"],
            last_used_at=item.get("last_used_at"),
            revoked_at=item.get("revoked_at"),
        )

    def create(self, name: str, rate_limit_per_minute: int, monthly_document_quota: int):
        import secrets

        clean_name = name.strip()
        if not clean_name:
            raise ApiKeyError("A key name is required.")
        raw_key = generate_key()
        record = ApiKeyRecord(
            id=secrets.token_hex(16),
            name=clean_name[:120],
            key_prefix=display_prefix(raw_key),
            rate_limit_per_minute=rate_limit_per_minute,
            monthly_document_quota=monthly_document_quota,
            created_at=utc_now_iso(),
            last_used_at=None,
            revoked_at=None,
        )
        self.keys.put_item(
            Item={
                "key_hash": hash_key(raw_key),
                "id": record.id,
                "name": record.name,
                "key_prefix": record.key_prefix,
                "rate_limit_per_minute": record.rate_limit_per_minute,
                "monthly_document_quota": record.monthly_document_quota,
                "created_at": record.created_at,
            }
        )
        return record, raw_key

    def find_by_raw_key(self, raw_key: str) -> ApiKeyRecord | None:
        item = self.keys.get_item(Key={"key_hash": hash_key(raw_key)}).get("Item")
        return self._record(item) if item else None

    def _item_by_id(self, key_id: str) -> dict | None:
        items = self.keys.scan().get("Items", [])
        return next((i for i in items if i.get("id") == key_id), None)

    def get(self, key_id: str) -> ApiKeyRecord | None:
        item = self._item_by_id(key_id)
        return self._record(item) if item else None

    def list_all(self) -> list[ApiKeyRecord]:
        items = self.keys.scan().get("Items", [])
        records = [self._record(i) for i in items]
        return sorted(records, key=lambda r: r.created_at, reverse=True)

    def revoke(self, key_id: str) -> bool:
        item = self._item_by_id(key_id)
        if item is None or item.get("revoked_at"):
            return False
        self.keys.update_item(
            Key={"key_hash": item["key_hash"]},
            UpdateExpression="SET revoked_at = :r",
            ExpressionAttributeValues={":r": utc_now_iso()},
        )
        return True

    def touch(self, key_id: str) -> None:
        item = self._item_by_id(key_id)
        if item is None:
            return
        self.keys.update_item(
            Key={"key_hash": item["key_hash"]},
            UpdateExpression="SET last_used_at = :t",
            ExpressionAttributeValues={":t": utc_now_iso()},
        )

    def documents_used(self, key_id: str, period: str | None = None) -> int:
        item = self.usage.get_item(
            Key={"api_key_id": key_id, "period": period or current_period()}
        ).get("Item")
        return int(item["documents"]) if item and "documents" in item else 0

    def record_documents(self, key_id: str, documents: int, pages: int = 0) -> None:
        if documents <= 0 and pages <= 0:
            return
        # ADD is atomic, so two containers counting at once cannot lose an increment.
        self.usage.update_item(
            Key={"api_key_id": key_id, "period": current_period()},
            UpdateExpression="ADD documents :d, pages :p",
            ExpressionAttributeValues={":d": max(documents, 0), ":p": max(pages, 0)},
        )

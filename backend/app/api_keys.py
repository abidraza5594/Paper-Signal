"""API key issuing, verification, rate limiting, and usage accounting.

Keys are shown to the caller exactly once at creation. Only a SHA-256 hash and a
short display prefix are stored, so a leaked database cannot be used to call the API.
"""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .models import ApiKeyPublic, utc_now_iso


KEY_PREFIX = "ps_live_"
KEY_BYTES = 24
PREFIX_DISPLAY_CHARS = 6


class ApiKeyError(RuntimeError):
    pass


class RateLimitExceeded(RuntimeError):
    def __init__(self, retry_after_seconds: int):
        super().__init__("Rate limit exceeded for this API key.")
        self.retry_after_seconds = retry_after_seconds


class QuotaExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class ApiKeyRecord:
    id: str
    name: str
    key_prefix: str
    rate_limit_per_minute: int
    monthly_document_quota: int
    created_at: str
    last_used_at: str | None
    revoked_at: str | None

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None

    def to_public(self, documents_this_month: int = 0) -> ApiKeyPublic:
        return ApiKeyPublic(
            id=self.id,
            name=self.name,
            key_prefix=self.key_prefix,
            rate_limit_per_minute=self.rate_limit_per_minute,
            monthly_document_quota=self.monthly_document_quota,
            documents_this_month=documents_this_month,
            created_at=self.created_at,
            last_used_at=self.last_used_at,
            revoked_at=self.revoked_at,
        )


def generate_key() -> str:
    return f"{KEY_PREFIX}{secrets.token_urlsafe(KEY_BYTES)}"


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def display_prefix(raw_key: str) -> str:
    return f"{KEY_PREFIX}{raw_key[len(KEY_PREFIX):][:PREFIX_DISPLAY_CHARS]}..."


def current_period() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.year:04d}-{now.month:02d}"


class ApiKeyStore:
    """SQLite-backed storage for keys and their per-month document usage."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.RLock()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS api_keys (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    key_prefix TEXT NOT NULL,
                    key_hash TEXT NOT NULL UNIQUE,
                    rate_limit_per_minute INTEGER NOT NULL,
                    monthly_document_quota INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    last_used_at TEXT,
                    revoked_at TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS api_key_usage (
                    api_key_id TEXT NOT NULL,
                    period TEXT NOT NULL,
                    documents INTEGER NOT NULL DEFAULT 0,
                    pages INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (api_key_id, period)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash)"
            )
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def create(
        self,
        name: str,
        rate_limit_per_minute: int,
        monthly_document_quota: int,
    ) -> tuple[ApiKeyRecord, str]:
        """Return the stored record plus the raw key, which is never recoverable later."""
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
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO api_keys
                    (id, name, key_prefix, key_hash, rate_limit_per_minute,
                     monthly_document_quota, created_at, last_used_at, revoked_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL)
                """,
                (
                    record.id,
                    record.name,
                    record.key_prefix,
                    hash_key(raw_key),
                    record.rate_limit_per_minute,
                    record.monthly_document_quota,
                    record.created_at,
                ),
            )
            connection.commit()
        return record, raw_key

    def find_by_raw_key(self, raw_key: str) -> ApiKeyRecord | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM api_keys WHERE key_hash = ?", (hash_key(raw_key),)
            ).fetchone()
        return self._row_to_record(row) if row else None

    def get(self, key_id: str) -> ApiKeyRecord | None:
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT * FROM api_keys WHERE id = ?", (key_id,)).fetchone()
        return self._row_to_record(row) if row else None

    def list_all(self) -> list[ApiKeyRecord]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM api_keys ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def revoke(self, key_id: str) -> bool:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "UPDATE api_keys SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
                (utc_now_iso(), key_id),
            )
            connection.commit()
            return cursor.rowcount > 0

    def touch(self, key_id: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "UPDATE api_keys SET last_used_at = ? WHERE id = ?", (utc_now_iso(), key_id)
            )
            connection.commit()

    def documents_used(self, key_id: str, period: str | None = None) -> int:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT documents FROM api_key_usage WHERE api_key_id = ? AND period = ?",
                (key_id, period or current_period()),
            ).fetchone()
        return int(row["documents"]) if row else 0

    def record_documents(self, key_id: str, documents: int, pages: int = 0) -> None:
        if documents <= 0 and pages <= 0:
            return
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO api_key_usage (api_key_id, period, documents, pages)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(api_key_id, period) DO UPDATE SET
                    documents = documents + excluded.documents,
                    pages = pages + excluded.pages
                """,
                (key_id, current_period(), max(documents, 0), max(pages, 0)),
            )
            connection.commit()

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> ApiKeyRecord:
        return ApiKeyRecord(
            id=row["id"],
            name=row["name"],
            key_prefix=row["key_prefix"],
            rate_limit_per_minute=int(row["rate_limit_per_minute"]),
            monthly_document_quota=int(row["monthly_document_quota"]),
            created_at=row["created_at"],
            last_used_at=row["last_used_at"],
            revoked_at=row["revoked_at"],
        )


class RateLimiter:
    """Sliding one-minute window per key.

    In-process only: with several API replicas each replica enforces its own share.
    Move this to Redis before running behind a load balancer.
    """

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key_id: str, limit_per_minute: int) -> None:
        now = time.monotonic()
        with self._lock:
            window = self._hits[key_id]
            while window and now - window[0] >= 60:
                window.popleft()
            if len(window) >= limit_per_minute:
                raise RateLimitExceeded(retry_after_seconds=max(1, int(60 - (now - window[0]))))
            window.append(now)

    def reset(self, key_id: str | None = None) -> None:
        with self._lock:
            if key_id is None:
                self._hits.clear()
            else:
                self._hits.pop(key_id, None)

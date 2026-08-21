from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "PDF Intelligence API"
    app_env: str = "local"
    data_dir: Path = Path("data")
    max_upload_mb: int = Field(default=200, ge=1, le=512)
    max_pdf_pages: int = Field(default=40, ge=1, le=500)
    max_batch_files: int = Field(default=10, ge=1, le=50)
    max_batch_total_mb: int = Field(default=500, ge=1, le=2048)
    max_pending_jobs: int = Field(default=100, ge=1, le=10000)
    local_worker_count: int = Field(default=10, ge=1, le=32)
    ai_max_retries: int = Field(default=3, ge=0, le=8)
    ai_retry_base_seconds: float = Field(default=1.0, ge=0.0, le=30.0)

    # API-as-a-service controls
    require_api_key: bool = False
    admin_token: SecretStr | None = None
    default_rate_limit_per_minute: int = Field(default=60, ge=1, le=10_000)
    default_monthly_document_quota: int = Field(default=1_000, ge=1, le=10_000_000)
    cors_origins: list[str] | str = ["http://localhost:4200"]

    mistral_api_key: SecretStr | None = None
    mistral_api_keys: SecretStr | None = None
    mistral_text_model: str = "mistral-small-2603"
    mistral_ocr_model: str = "mistral-ocr-4-0"

    ocr_min_text_chars: int = Field(default=80, ge=0, le=2000)
    vision_min_text_chars: int = Field(default=40, ge=1, le=2000)
    vision_render_dpi: int = Field(default=144, ge=72, le=300)
    text_chunk_chars: int = Field(default=50_000, ge=5_000, le=200_000)
    ocr_page_batch_size: int = Field(default=40, ge=1, le=100)
    merge_batch_size: int = Field(default=8, ge=2, le=20)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def max_batch_total_bytes(self) -> int:
        return self.max_batch_total_mb * 1024 * 1024

    @property
    def admin_token_value(self) -> str | None:
        token = self.admin_token.get_secret_value().strip() if self.admin_token else ""
        return token or None

    @property
    def api_keys_database_path(self) -> Path:
        return self.data_dir / "api_keys.sqlite3"

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "jobs.sqlite3"

    @property
    def ai_configured(self) -> bool:
        return bool(self.mistral_key_values)

    @property
    def mistral_key_values(self) -> list[str]:
        """Return unique keys in failover order without exposing them in settings output."""
        values: list[str] = []
        if self.mistral_api_keys:
            values.extend(self.mistral_api_keys.get_secret_value().split(","))
        if self.mistral_api_key:
            values.append(self.mistral_api_key.get_secret_value())

        unique: list[str] = []
        for value in values:
            cleaned = value.strip()
            if cleaned and cleaned not in unique:
                unique.append(cleaned)
        return unique

    def prepare_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()

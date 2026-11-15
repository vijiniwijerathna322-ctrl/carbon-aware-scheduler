"""Typed environment settings with stable project-relative paths."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_project_root() -> Path:
    for directory in Path(__file__).resolve().parents:
        if (directory / "pyproject.toml").is_file():
            return directory
    return Path.cwd().resolve()


PROJECT_ROOT = _find_project_root()


class MissingApiKeyError(RuntimeError):
    """A command needing EIA data has no configured API key."""


class Settings(BaseSettings):
    """Application configuration; constructing settings does not require a key."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", extra="ignore", populate_by_name=True
    )

    eia_api_key: SecretStr | None = Field(default=None, validation_alias="EIA_API_KEY")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", validation_alias="LOG_LEVEL"
    )
    data_dir: Path = Field(default=PROJECT_ROOT / "data", validation_alias="CARBON_DATA_DIR")
    models_dir: Path = Field(default=PROJECT_ROOT / "models", validation_alias="CARBON_MODELS_DIR")
    reports_dir: Path = Field(
        default=PROJECT_ROOT / "reports", validation_alias="CARBON_REPORTS_DIR"
    )
    regions_path: Path = Field(
        default=PROJECT_ROOT / "config/regions.yaml", validation_alias="CARBON_REGIONS_PATH"
    )
    demo_mode: bool = Field(default=False, validation_alias="DEMO_MODE")
    max_data_age_hours: float = Field(
        default=6, gt=0, allow_inf_nan=False, validation_alias="MAX_DATA_AGE_HOURS"
    )
    api_keys: str | None = Field(default=None, validation_alias="API_KEYS")
    rate_limit_per_minute: int = Field(default=60, gt=0, validation_alias="RATE_LIMIT_PER_MINUTE")
    cors_allowed_origins: str | None = Field(default=None, validation_alias="CORS_ALLOWED_ORIGINS")
    monitor_webhook_url: str | None = Field(default=None, validation_alias="MONITOR_WEBHOOK_URL")
    monitor_webhook_style: Literal["generic", "slack"] = Field(
        default="generic", validation_alias="MONITOR_WEBHOOK_STYLE"
    )

    def api_key_set(self) -> set[str]:
        """Configured keys, or an empty set when auth is disabled."""
        if not self.api_keys:
            return set()
        return {key.strip() for key in self.api_keys.split(",") if key.strip()}

    def cors_origin_list(self) -> list[str]:
        if not self.cors_allowed_origins:
            return []
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @field_validator("eia_api_key", mode="before")
    @classmethod
    def empty_key_is_missing(cls, value: str | SecretStr | None) -> str | SecretStr | None:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("data_dir", "models_dir", "reports_dir", "regions_path")
    @classmethod
    def resolve_directory(cls, value: Path) -> Path:
        return (PROJECT_ROOT / value).resolve() if not value.is_absolute() else value

    def require_eia_key(self) -> str:
        """Return the key only when an operation actually needs EIA access."""
        if self.eia_api_key is None:
            raise MissingApiKeyError("Set EIA_API_KEY in the environment or project .env file.")
        return self.eia_api_key.get_secret_value()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load configuration once per process."""
    return Settings()

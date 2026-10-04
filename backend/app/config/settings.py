from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, read from environment variables or a .env file.

    The .env file is looked up in the current directory and its parent, so the backend
    works whether it is started from the repo root or from backend/.
    """

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    database_url: PostgresDsn = Field(
        default=PostgresDsn(
            "postgresql+psycopg://roc:roc_dev_password@localhost:5432/roc_verifier"
        ),
    )
    database_connect_timeout_seconds: int = Field(default=3, ge=1, le=30)

    # Which ROC data source the verification engine uses. Only the mock provider exists so far.
    roc_provider: Literal["mock"] = "mock"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()

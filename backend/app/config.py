"""Application settings, read from environment variables (and an optional .env file).

No secrets live in code: GOOGLE_API_KEY and DATABASE_URL come from the environment
(locally from `.env`, on Cloud Run from Secret Manager-backed env vars).
"""

from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # SQLite for local dev; prod uses e.g.
    # mssql+pyodbc://user:pass@host:1433/kasa?driver=ODBC+Driver+18+for+SQL+Server
    database_url: str = "sqlite:///./kasa.db"

    # Gemini via Google AI Studio key. Agent endpoints return 503 while this is empty.
    google_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # Comma-separated list in the env var, e.g. "http://localhost:3000,https://kasa.web.app"
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    # Sprint-1 dev auth: requests without X-User-Id act as this user.
    dev_default_user_id: str = "dev-user"

    # Upper bound on rows the report agent's SQL tool may return.
    report_row_limit: int = 200

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [o.strip() for o in value.split(",") if o.strip()]
        return value

    @property
    def agents_enabled(self) -> bool:
        return bool(self.google_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()

"""Application settings, read from environment variables (and an optional .env file).

No secrets live in code: API keys, OAuth secrets, the token encryption key and DATABASE_URL
come from the environment (locally from `.env`, on Cloud Run from Secret Manager-backed
env vars). Every track's settings live here so feature code never edits this file.
"""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Database ---------------------------------------------------------------------------
    # SQLite for local dev; prod uses e.g.
    # mssql+pyodbc://user:pass@host:1433/kasa?driver=ODBC+Driver+18+for+SQL+Server
    database_url: str = "sqlite:///./kasa.db"
    # Run `alembic upgrade head` on startup. Turn off in prod, where the app's low-privilege
    # login cannot run DDL; run migrations as a separate step with an admin URL instead.
    auto_migrate: bool = True

    # --- LLM provider -----------------------------------------------------------------------
    # "gemini" is the product default. "ollama" is for dev/tests against a local or LAN
    # Ollama server through ADK's LiteLLM wrapper.
    llm_provider: Literal["gemini", "ollama"] = "gemini"
    # Gemini via Google AI Studio key. With llm_provider=gemini, agent endpoints return 503
    # while this is empty.
    google_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_vision_model: str = ""  # empty = same as gemini_model
    ollama_base_url: str = ""  # e.g. http://localhost:11434
    ollama_model: str = "gpt-oss:20b"  # text + tool calling (chat, house, report, budget, inbox)
    ollama_vision_model: str = "qwen3-vl:8b"  # receipts and other images
    # How long Ollama keeps a model in memory after our last call. Explicit so a shared
    # server is not left holding our models forever.
    ollama_keep_alive: str = "10m"
    # Text model only, passed as LiteLLM reasoning_effort ("low" = Ollama think=low for
    # gpt-oss, think on for other thinking models; "none" = off; empty = model default).
    ollama_reasoning_effort: str = "low"

    # --- HTTP -------------------------------------------------------------------------------
    # Comma-separated list in the env var, e.g. "http://localhost:3000,https://kasa.web.app"
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    # Where the web UI lives (OAuth callbacks redirect back here).
    frontend_url: str = "http://localhost:3000"

    # --- Auth -------------------------------------------------------------------------------
    # Set to require Firebase ID tokens (Authorization: Bearer ...). Empty = dev mode, where
    # the X-User-Id header (or dev_default_user_id) says who is calling.
    firebase_project_id: str = ""
    dev_default_user_id: str = "dev-user"

    # --- Google OAuth (Gmail + Calendar for one user) ---------------------------------------
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_uri: str = "http://localhost:8000/integrations/google/callback"
    google_oauth_scopes: Annotated[list[str], NoDecode] = [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/calendar.events",
    ]
    # Fernet key that encrypts stored refresh tokens. Generate with
    # `python -m app.services.crypto`. Required once Google accounts can be connected.
    token_encryption_key: str = ""

    # --- Gmail sync -------------------------------------------------------------------------
    gmail_query: str = (
        "newer_than:30d -category:social subject:(sipariş OR siparis OR order OR fatura OR invoice"
        ' OR makbuz OR receipt OR dekont OR harcama OR "kartınızdan" OR "e-arşiv" OR ödeme)'
    )
    gmail_sync_max_messages: int = 50
    # Pub/Sub topic Gmail publishes to (projects/<project>/topics/<topic>) and the push
    # subscription's OIDC settings, checked on POST /internal/gmail/push.
    pubsub_topic: str = ""
    pubsub_push_audience: str = ""
    pubsub_push_service_account: str = ""

    # --- Internal endpoints (Cloud Scheduler) -----------------------------------------------
    # Shared secret sent as X-Kasa-Task-Token. Empty disables /internal/* (503).
    internal_task_token: str = ""

    # --- Money ------------------------------------------------------------------------------
    base_currency: str = "TRY"
    tcmb_base_url: str = "https://www.tcmb.gov.tr/kurlar"

    # --- Uploads ----------------------------------------------------------------------------
    max_upload_bytes: int = 10 * 1024 * 1024

    # --- Reports ----------------------------------------------------------------------------
    # Upper bound on rows the report agent's SQL tool may return.
    report_row_limit: int = 200

    @field_validator("cors_origins", "google_oauth_scopes", mode="before")
    @classmethod
    def _split_list(cls, value: object) -> object:
        if isinstance(value, str):
            return [o.strip() for o in value.replace(" ", ",").split(",") if o.strip()]
        return value

    @property
    def agents_enabled(self) -> bool:
        if self.llm_provider == "ollama":
            return bool(self.ollama_base_url)
        return bool(self.google_api_key)

    @property
    def vision_model_name(self) -> str:
        if self.llm_provider == "ollama":
            return self.ollama_vision_model
        return self.gemini_vision_model or self.gemini_model

    @property
    def chat_model_name(self) -> str:
        return self.ollama_model if self.llm_provider == "ollama" else self.gemini_model

    @property
    def google_oauth_enabled(self) -> bool:
        return bool(
            self.google_oauth_client_id and self.google_oauth_client_secret and self.token_encryption_key
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()

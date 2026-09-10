from __future__ import annotations

import logging
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

INSECURE_SECRETS = {"change-me-in-production", "secret", "changeme", ""}


class Settings(BaseSettings):
    """Application settings.

    Every value is overridable via environment variables (or `backend/.env`).
    Nothing that differs between environments should ever be hardcoded elsewhere.
    """

    # Always the backend's own .env, whatever the working directory is. Running
    # pytest / alembic / uvicorn from the repo root used to silently pick up a
    # different .env and load the wrong database driver.
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Runtime ---------------------------------------------------------
    ENVIRONMENT: str = "development"
    # Alias: some tooling (CI, compose) sets `ENV` instead of `ENVIRONMENT`.
    ENV: str | None = None
    LOG_LEVEL: str = "INFO"
    APP_VERSION: str = "2.0.0"

    # --- Database --------------------------------------------------------
    DATABASE_URL: str = "postgresql+asyncpg://chadev:chadev@localhost:5432/chadev_buchhaltung"
    DATABASE_URL_SYNC: str = "postgresql://chadev:chadev@localhost:5432/chadev_buchhaltung"
    # In dev/test we bootstrap tables from the models. In production Alembic owns
    # the schema, so this must stay off.
    AUTO_CREATE_TABLES: bool | None = None

    # --- Auth ------------------------------------------------------------
    SECRET_KEY: str = "change-me-in-production"
    # Alias so `JWT_SECRET` (used by CI / docker-compose / README) also works.
    JWT_SECRET: str | None = None
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    ALGORITHM: str = "HS256"

    # --- Rate limiting ---------------------------------------------------
    # slowapi limit strings ("<count>/<period>"). Requests are keyed per tenant
    # when they carry a valid Bearer token and per client IP otherwise
    # (`core/rate_limit.py`). DEFAULT applies to every route; CLASSIFY to the
    # ML inference routes; HEAVY to routes that run OCR/vision, PDF parsing,
    # model training or an LLM call.
    RATE_LIMIT_DEFAULT: str = "200/minute"
    RATE_LIMIT_CLASSIFY: str = "60/minute"
    RATE_LIMIT_HEAVY: str = "30/minute"

    # --- CORS ------------------------------------------------------------
    # Comma-separated list, e.g. "https://app.example.ch,https://admin.example.ch"
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # --- Email -----------------------------------------------------------
    SMTP_HOST: str = ""
    SMTP_PORT: int = 465
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    FROM_EMAIL: str = ""

    # --- AI / Ollama -----------------------------------------------------
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    # Preferred text/chat model for the AI assistant. Leave empty to auto-detect
    # a suitable chat model from Ollama's installed models (vision models are
    # excluded, since the assistant is text-only).
    OLLAMA_CHAT_MODEL: str = ""

    FRONTEND_URL: str = "http://localhost:3000"
    SENTRY_DSN: str | None = None

    # --- Storage (uploads, model artifacts) --------------------------------
    # "local" writes under STORAGE_LOCAL_DIR (fine for one replica); "s3" is
    # required as soon as the API runs with more than one replica.
    STORAGE_BACKEND: str = "local"
    STORAGE_LOCAL_DIR: str = "/app/data"
    S3_BUCKET: str = ""
    # Leave empty for AWS; set for MinIO / R2 / any S3-compatible endpoint.
    S3_ENDPOINT_URL: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_REGION: str = ""

    # --- Derived ---------------------------------------------------------
    @model_validator(mode="after")
    def _resolve_and_validate(self) -> Settings:
        if self.ENV and self.ENVIRONMENT == "development":
            object.__setattr__(self, "ENVIRONMENT", self.ENV)

        # JWT_SECRET wins if explicitly provided (keeps CI/README/compose honest).
        if self.JWT_SECRET:
            object.__setattr__(self, "SECRET_KEY", self.JWT_SECRET)

        if self.AUTO_CREATE_TABLES is None:
            object.__setattr__(self, "AUTO_CREATE_TABLES", not self.is_production)

        if self.is_production:
            problems: list[str] = []
            if self.SECRET_KEY.strip().lower() in INSECURE_SECRETS or len(self.SECRET_KEY) < 32:
                problems.append("SECRET_KEY (or JWT_SECRET) must be set to a random value of >=32 chars")
            if "*" in self.CORS_ORIGINS:
                problems.append("CORS_ORIGINS must not contain '*' in production")
            if self.AUTO_CREATE_TABLES:
                problems.append("AUTO_CREATE_TABLES must be false in production (Alembic owns the schema)")
            if self.STORAGE_BACKEND.strip().lower() == "s3" and not self.S3_BUCKET:
                problems.append("S3_BUCKET must be set when STORAGE_BACKEND=s3")
            if problems:
                raise ValueError(
                    "Refusing to start in production with an unsafe configuration:\n  - " + "\n  - ".join(problems)
                )
        elif self.SECRET_KEY.strip().lower() in INSECURE_SECRETS:
            logger.warning("[config] Using the default SECRET_KEY — fine for dev, never for production.")
        return self

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.strip().lower() in {"production", "prod"}

    @property
    def is_test(self) -> bool:
        return self.ENVIRONMENT.strip().lower() in {"test", "testing", "ci"}

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()

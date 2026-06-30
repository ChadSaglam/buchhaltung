from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://chadev:chadev@localhost:5432/chadev_buchhaltung"
    DATABASE_URL_SYNC: str = "postgresql://chadev:chadev@localhost:5432/chadev_buchhaltung"
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    ALGORITHM: str = "HS256"

    SMTP_HOST: str = ""
    SMTP_PORT: int = 465
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    FROM_EMAIL: str = ""

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    FRONTEND_URL: str = "http://localhost:3000"

    SENTRY_DSN: str | None = None
    ENVIRONMENT: str = "development"


settings = Settings()
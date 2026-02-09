import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_version: str
    api_prefix: str
    log_level: str
    database_url: str


def _load_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "Metacognitive Interview API"),
        app_version=os.getenv("APP_VERSION", "0.1.0"),
        api_prefix=os.getenv("API_PREFIX", "/api/v1"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@localhost:5432/interview",
        ),
    )


settings = _load_settings()

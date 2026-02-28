import os
from dataclasses import dataclass

from libs.env_loader import load_project_env

load_project_env()


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_version: str
    api_prefix: str
    log_level: str
    database_url: str
    auth_token_secret: str
    access_token_ttl_seconds: int
    admin_login_email: str
    admin_login_password: str
    annotator_login_email: str
    annotator_login_password: str
    allow_remote_audio_fetch: bool
    remote_audio_max_bytes: int
    remote_audio_allowed_hosts: tuple[str, ...]


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _as_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    if parsed <= 0:
        return default
    return parsed


def _as_csv(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    return tuple(item.strip().lower() for item in value.split(",") if item.strip())


def _load_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "Metacognitive Interview API"),
        app_version=os.getenv("APP_VERSION", "0.1.0"),
        api_prefix=os.getenv("API_PREFIX", "/api/v1"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        database_url=os.getenv(
            "DATABASE_URL",
            "sqlite+pysqlite:///./interview.db",
        ),
        auth_token_secret=os.getenv("AUTH_TOKEN_SECRET", "dev-auth-secret"),
        access_token_ttl_seconds=_as_int(os.getenv("ACCESS_TOKEN_TTL_SECONDS"), default=3600),
        admin_login_email=os.getenv("ADMIN_LOGIN_EMAIL", "admin@company.com"),
        admin_login_password=os.getenv("ADMIN_LOGIN_PASSWORD", "password123"),
        annotator_login_email=os.getenv("ANNOTATOR_LOGIN_EMAIL", "annotator@company.com"),
        annotator_login_password=os.getenv("ANNOTATOR_LOGIN_PASSWORD", "password123"),
        allow_remote_audio_fetch=_as_bool(os.getenv("ALLOW_REMOTE_AUDIO_FETCH"), default=False),
        remote_audio_max_bytes=_as_int(os.getenv("REMOTE_AUDIO_MAX_BYTES"), default=10 * 1024 * 1024),
        remote_audio_allowed_hosts=_as_csv(os.getenv("REMOTE_AUDIO_ALLOWED_HOSTS")),
    )


settings = _load_settings()

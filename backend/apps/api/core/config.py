import os
from dataclasses import dataclass
from pathlib import Path

from libs.env_loader import load_project_env

load_project_env()

BACKEND_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CANDIDATE_REGISTRY = BACKEND_ROOT / "data" / "candidates" / "dev_candidates.json"
DEFAULT_DATABASE_URL = "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/interview"


@dataclass(frozen=True)
class Settings:
    app_env: str
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
    candidate_registry_path: str
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


def _normalize_env(value: str | None) -> str:
    normalized = (value or "dev").strip().lower()
    return normalized or "dev"


def _validate_database_url(database_url: str) -> str:
    normalized = database_url.strip()
    if not normalized:
        raise ValueError("DATABASE_URL must not be empty")
    if not normalized.startswith("postgresql"):
        raise ValueError("DATABASE_URL must use a PostgreSQL URL; SQLite is not supported")
    return normalized


def _validate_settings(settings: Settings) -> Settings:
    database_url = _validate_database_url(settings.database_url)
    if not settings.candidate_registry_path.strip():
        raise ValueError("CANDIDATE_REGISTRY_PATH must not be empty")
    candidate_registry = Path(settings.candidate_registry_path)
    if not candidate_registry.is_absolute():
        candidate_registry = (BACKEND_ROOT / candidate_registry).resolve()
    if not candidate_registry.is_file():
        raise ValueError(f"CANDIDATE_REGISTRY_PATH does not exist: {candidate_registry}")

    if settings.app_env != "dev":
        if not settings.auth_token_secret.strip() or settings.auth_token_secret == "dev-auth-secret":
            raise ValueError("AUTH_TOKEN_SECRET must be set to a non-dev value when APP_ENV is not dev")
        if not settings.admin_login_password.strip() or settings.admin_login_password == "password123":
            raise ValueError("ADMIN_LOGIN_PASSWORD must be set to a non-default value when APP_ENV is not dev")
        if not settings.annotator_login_password.strip() or settings.annotator_login_password == "password123":
            raise ValueError("ANNOTATOR_LOGIN_PASSWORD must be set to a non-default value when APP_ENV is not dev")

    return Settings(
        app_env=settings.app_env,
        app_name=settings.app_name,
        app_version=settings.app_version,
        api_prefix=settings.api_prefix,
        log_level=settings.log_level,
        database_url=database_url,
        auth_token_secret=settings.auth_token_secret,
        access_token_ttl_seconds=settings.access_token_ttl_seconds,
        admin_login_email=settings.admin_login_email,
        admin_login_password=settings.admin_login_password,
        annotator_login_email=settings.annotator_login_email,
        annotator_login_password=settings.annotator_login_password,
        candidate_registry_path=settings.candidate_registry_path,
        allow_remote_audio_fetch=settings.allow_remote_audio_fetch,
        remote_audio_max_bytes=settings.remote_audio_max_bytes,
        remote_audio_allowed_hosts=settings.remote_audio_allowed_hosts,
    )


def _load_settings() -> Settings:
    return _validate_settings(
        Settings(
            app_env=_normalize_env(os.getenv("APP_ENV")),
            app_name=os.getenv("APP_NAME", "Metacognitive Interview API"),
            app_version=os.getenv("APP_VERSION", "0.1.0"),
            api_prefix=os.getenv("API_PREFIX", "/api/v1"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            database_url=os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL),
            auth_token_secret=os.getenv("AUTH_TOKEN_SECRET", "dev-auth-secret"),
            access_token_ttl_seconds=_as_int(os.getenv("ACCESS_TOKEN_TTL_SECONDS"), default=3600),
            admin_login_email=os.getenv("ADMIN_LOGIN_EMAIL", "admin@company.com"),
            admin_login_password=os.getenv("ADMIN_LOGIN_PASSWORD", "password123"),
            annotator_login_email=os.getenv("ANNOTATOR_LOGIN_EMAIL", "annotator@company.com"),
            annotator_login_password=os.getenv("ANNOTATOR_LOGIN_PASSWORD", "password123"),
            candidate_registry_path=os.getenv("CANDIDATE_REGISTRY_PATH", str(DEFAULT_CANDIDATE_REGISTRY)),
            allow_remote_audio_fetch=_as_bool(os.getenv("ALLOW_REMOTE_AUDIO_FETCH"), default=False),
            remote_audio_max_bytes=_as_int(os.getenv("REMOTE_AUDIO_MAX_BYTES"), default=10 * 1024 * 1024),
            remote_audio_allowed_hosts=_as_csv(os.getenv("REMOTE_AUDIO_ALLOWED_HOSTS")),
        )
    )


settings = _load_settings()

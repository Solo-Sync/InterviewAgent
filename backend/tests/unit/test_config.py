import pytest

from apps.api.core import config as config_module


def test_non_dev_requires_non_default_auth_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.delenv("AUTH_TOKEN_SECRET", raising=False)
    monkeypatch.setenv("ADMIN_LOGIN_PASSWORD", "secure-admin-password")
    monkeypatch.setenv("ANNOTATOR_LOGIN_PASSWORD", "secure-annotator-password")

    with pytest.raises(ValueError, match="AUTH_TOKEN_SECRET"):
        config_module._load_settings()


def test_non_dev_requires_non_default_admin_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("AUTH_TOKEN_SECRET", "prod-secret-value")
    monkeypatch.setenv("ADMIN_LOGIN_PASSWORD", "password123")
    monkeypatch.setenv("ANNOTATOR_LOGIN_PASSWORD", "secure-annotator-password")

    with pytest.raises(ValueError, match="ADMIN_LOGIN_PASSWORD"):
        config_module._load_settings()


def test_non_dev_requires_non_default_annotator_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("AUTH_TOKEN_SECRET", "prod-secret-value")
    monkeypatch.setenv("ADMIN_LOGIN_PASSWORD", "secure-admin-password")
    monkeypatch.setenv("ANNOTATOR_LOGIN_PASSWORD", "password123")

    with pytest.raises(ValueError, match="ANNOTATOR_LOGIN_PASSWORD"):
        config_module._load_settings()


def test_database_url_must_use_postgresql(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///./interview.db")

    with pytest.raises(ValueError, match="PostgreSQL URL"):
        config_module._load_settings()

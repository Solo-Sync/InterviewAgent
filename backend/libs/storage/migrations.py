from __future__ import annotations

import re
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI_PATH = BACKEND_ROOT / "alembic.ini"
MIGRATIONS_PATH = BACKEND_ROOT / "migrations"
_SCHEMA_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


def make_alembic_config(database_url: str) -> Config:
    config = Config(str(ALEMBIC_INI_PATH))
    config.set_main_option("script_location", str(MIGRATIONS_PATH))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    config.attributes["database_url"] = database_url
    return config


def upgrade_database(database_url: str, revision: str = "head") -> None:
    _ensure_search_path_schema(database_url)
    command.upgrade(make_alembic_config(database_url), revision)


def _ensure_search_path_schema(database_url: str) -> None:
    url = make_url(database_url)
    options = (url.query.get("options") or "").split()
    schema_name: str | None = None
    for option in options:
        if option.startswith("-csearch_path="):
            schema_name = option.split("=", 1)[1].strip()
            break

    if not schema_name:
        return
    if not _SCHEMA_NAME_RE.fullmatch(schema_name):
        raise ValueError(f"Invalid PostgreSQL schema name in DATABASE_URL search_path: {schema_name}")

    admin_engine = create_engine(url.set(query={}), future=True, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
    finally:
        admin_engine.dispose()

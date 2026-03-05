from __future__ import annotations

import os
import re
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from libs.storage.migrations import upgrade_database

DEFAULT_TEST_DATABASE_URL = "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/interview_test"
SHARED_TEST_SCHEMA = "pytest"
_IDENTIFIER_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


def base_test_database_url() -> str:
    return os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL") or DEFAULT_TEST_DATABASE_URL


def shared_test_schema() -> str:
    return os.getenv("TEST_DATABASE_SCHEMA", SHARED_TEST_SCHEMA)


def schema_database_url(schema: str) -> str:
    _validate_identifier(schema)
    url = make_url(base_test_database_url())
    query = dict(url.query)
    options = query.get("options", "").strip()
    search_path_option = f"-csearch_path={schema}"
    query["options"] = f"{options} {search_path_option}".strip() if options else search_path_option
    return url.set(query=query).render_as_string(hide_password=False)


def unique_schema(prefix: str) -> str:
    sanitized = re.sub(r"[^a-z0-9_]+", "_", prefix.lower()).strip("_") or "pytest"
    return f"{sanitized}_{uuid4().hex[:8]}"


def drop_and_create_schema(schema: str) -> None:
    _validate_identifier(schema)
    engine = create_engine(base_test_database_url(), future=True, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    finally:
        engine.dispose()


def drop_schema(schema: str) -> None:
    _validate_identifier(schema)
    engine = create_engine(base_test_database_url(), future=True, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    finally:
        engine.dispose()


def migrate_schema(schema: str) -> str:
    database_url = schema_database_url(schema)
    upgrade_database(database_url)
    return database_url


def provision_schema(schema: str) -> str:
    drop_and_create_schema(schema)
    return migrate_schema(schema)


def truncate_schema(schema: str) -> None:
    _validate_identifier(schema)
    engine = create_engine(schema_database_url(schema), future=True)
    try:
        with engine.begin() as conn:
            table_names = [
                row[0]
                for row in conn.execute(
                    text(
                        """
                        SELECT tablename
                        FROM pg_tables
                        WHERE schemaname = current_schema()
                          AND tablename <> 'alembic_version'
                        ORDER BY tablename
                        """
                    )
                )
            ]
            if not table_names:
                return
            joined_tables = ", ".join(f'"{table_name}"' for table_name in table_names)
            conn.execute(text(f"TRUNCATE TABLE {joined_tables} RESTART IDENTITY CASCADE"))
    finally:
        engine.dispose()


def _validate_identifier(value: str) -> None:
    if not _IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"Invalid PostgreSQL identifier: {value}")

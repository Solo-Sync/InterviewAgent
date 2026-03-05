from __future__ import annotations

from sqlalchemy import inspect

from libs.storage.migrations import upgrade_database
from libs.storage.postgres import SqlStore
from tests.support.postgres import drop_schema, schema_database_url, unique_schema

EXPECTED_TABLES = {"sessions", "turns", "events", "reports", "annotations"}


def test_sql_store_does_not_create_schema_implicitly() -> None:
    schema = unique_schema("no_auto_create")
    database_url = schema_database_url(schema)

    try:
        drop_schema(schema)
        store = SqlStore(database_url)
        try:
            table_names = set(inspect(store.engine).get_table_names(schema=schema))
        finally:
            store.engine.dispose()
    finally:
        drop_schema(schema)

    assert EXPECTED_TABLES.isdisjoint(table_names)


def test_upgrade_database_creates_expected_schema() -> None:
    schema = unique_schema("migrated")
    database_url = schema_database_url(schema)

    try:
        drop_schema(schema)
        upgrade_database(database_url)
        store = SqlStore(database_url)
        try:
            table_names = set(inspect(store.engine).get_table_names(schema=schema))
        finally:
            store.engine.dispose()
    finally:
        drop_schema(schema)

    assert EXPECTED_TABLES.issubset(table_names)
    assert "alembic_version" in table_names

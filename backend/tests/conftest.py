from __future__ import annotations

import os

import pytest

from tests.support.postgres import (
    DEFAULT_TEST_DATABASE_URL,
    provision_schema,
    schema_database_url,
    shared_test_schema,
    truncate_schema,
)

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
TEST_DATABASE_SCHEMA = shared_test_schema()

os.environ["TEST_DATABASE_URL"] = TEST_DATABASE_URL
os.environ["DATABASE_URL"] = schema_database_url(TEST_DATABASE_SCHEMA)


def pytest_configure() -> None:
    try:
        provision_schema(TEST_DATABASE_SCHEMA)
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.exit(f"PostgreSQL test database is unavailable: {exc}")


@pytest.fixture(autouse=True)
def reset_database() -> None:
    truncate_schema(TEST_DATABASE_SCHEMA)

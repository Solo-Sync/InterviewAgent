from __future__ import annotations

import shutil
import os
from pathlib import Path

import pytest

from services.safety.prompt_injection_detector import PromptInjectionCheck, PromptInjectionDetector
from tests.support.postgres import (
    DEFAULT_TEST_DATABASE_URL,
    provision_schema,
    schema_database_url,
    shared_test_schema,
    truncate_schema,
)

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)
TEST_DATABASE_SCHEMA = shared_test_schema()
BACKEND_ROOT = Path(__file__).resolve().parents[1]
QUESTION_SET_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "question_sets"
QUESTION_SET_DIR = BACKEND_ROOT / "data" / "question_sets"

os.environ["TEST_DATABASE_URL"] = TEST_DATABASE_URL
os.environ["DATABASE_URL"] = schema_database_url(TEST_DATABASE_SCHEMA)


def pytest_configure() -> None:
    _install_question_set_fixtures()
    try:
        provision_schema(TEST_DATABASE_SCHEMA)
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.exit(f"PostgreSQL test database is unavailable: {exc}")


@pytest.fixture(autouse=True)
def reset_database() -> None:
    truncate_schema(TEST_DATABASE_SCHEMA)


@pytest.fixture(autouse=True)
def mock_prompt_injection_detector(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    if request.node.fspath.basename == "test_prompt_injection_detector.py":
        return
    monkeypatch.setattr(
        PromptInjectionDetector,
        "detect",
        lambda self, _text: PromptInjectionCheck(  # noqa: ARG005
            is_prompt_injection=False,
            confidence=0.0,
            category="none",
            reason="normal",
        ),
    )


def _install_question_set_fixtures() -> None:
    QUESTION_SET_DIR.mkdir(parents=True, exist_ok=True)
    for fixture_path in QUESTION_SET_FIXTURES.glob("*.json"):
        shutil.copyfile(fixture_path, QUESTION_SET_DIR / fixture_path.name)

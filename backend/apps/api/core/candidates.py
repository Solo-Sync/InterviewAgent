from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from typing import Final

from apps.api.core.config import settings
from libs.storage.postgres import CandidateAccountRecord, SqlStore

_USERNAME_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9]{1,20}$")
_PASSWORD_ALLOWED_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9@_]{8,20}$")
_PASSWORD_HASH_ALGORITHM = "pbkdf2_sha256"
_PASSWORD_HASH_ITERATIONS = 200_000
_store = SqlStore(settings.database_url)


@dataclass(frozen=True)
class CandidateIdentity:
    username: str
    candidate_id: str
    display_name: str
    active: bool = True


def validate_candidate_username(username: str) -> str:
    normalized = username.strip()
    if not _USERNAME_RE.fullmatch(normalized):
        raise ValueError("username must be 1-20 characters of letters and digits only")
    return normalized


def validate_candidate_password(password: str) -> str:
    if not _PASSWORD_ALLOWED_RE.fullmatch(password):
        raise ValueError(
            "password must be 8-20 characters and only contain letters, digits, @, or _"
        )
    has_letter = any(char.isalpha() for char in password)
    has_digit = any(char.isdigit() for char in password)
    has_special = any(char in "@_" for char in password)
    if not (has_letter and has_digit and has_special):
        raise ValueError("password must include letters, digits, and at least one of @ or _")
    return password


def register_candidate(username: str, password: str) -> CandidateIdentity:
    normalized_username = validate_candidate_username(username)
    validate_candidate_password(password)
    password_hash = _hash_password(password)
    with _store.transaction() as db:
        _store.create_candidate_account(
            db,
            username=normalized_username,
            password_hash=password_hash,
            display_name=normalized_username,
            is_active=True,
        )
    return CandidateIdentity(
        username=normalized_username,
        candidate_id=normalized_username,
        display_name=normalized_username,
        active=True,
    )


def authenticate_candidate(username: str, password: str) -> CandidateIdentity | None:
    normalized_username = username.strip()
    if not normalized_username or not password:
        return None

    account = _store.get_candidate_account(normalized_username)
    if account is None or not account.is_active:
        return None
    if not _verify_password(password, account.password_hash):
        return None
    return _identity_from_account(account)


def _identity_from_account(account: CandidateAccountRecord) -> CandidateIdentity:
    return CandidateIdentity(
        username=account.username,
        candidate_id=account.username,
        display_name=account.display_name or account.username,
        active=account.is_active,
    )


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        _PASSWORD_HASH_ITERATIONS,
    )
    return "$".join(
        [
            _PASSWORD_HASH_ALGORITHM,
            str(_PASSWORD_HASH_ITERATIONS),
            _b64encode(salt),
            _b64encode(digest),
        ]
    )


def _verify_password(password: str, encoded_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt_text, digest_text = encoded_hash.split("$", 3)
        iterations = int(iterations_text)
    except ValueError:
        return False
    if algorithm != _PASSWORD_HASH_ALGORITHM or iterations <= 0:
        return False
    try:
        salt = _b64decode(salt_text)
        expected_digest = _b64decode(digest_text)
    except ValueError:
        return False
    actual_digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual_digest, expected_digest)


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)

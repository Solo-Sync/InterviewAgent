from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from enum import Enum
from time import time
from typing import Any

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ValidationError

from apps.api.core.config import settings

bearer_scheme = HTTPBearer(auto_error=False)


class AuthRole(str, Enum):
    CANDIDATE = "candidate"
    ADMIN = "admin"
    ANNOTATOR = "annotator"


class AccessTokenClaims(BaseModel):
    sub: str
    role: AuthRole
    exp: int
    iat: int
    candidate_id: str | None = None
    display_name: str | None = None


@dataclass(frozen=True)
class AuthPrincipal:
    subject: str
    role: AuthRole
    candidate_id: str | None = None
    display_name: str | None = None
    expires_at: int = 0


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _json_dumps(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _sign(message: bytes) -> str:
    digest = hmac.new(settings.auth_token_secret.encode("utf-8"), message, hashlib.sha256).digest()
    return _b64url_encode(digest)


def issue_access_token(
    *,
    subject: str,
    role: AuthRole,
    candidate_id: str | None = None,
    display_name: str | None = None,
    ttl_seconds: int | None = None,
) -> tuple[str, int]:
    now = int(time())
    expires_in = ttl_seconds or settings.access_token_ttl_seconds
    claims = AccessTokenClaims(
        sub=subject,
        role=role,
        candidate_id=candidate_id,
        display_name=display_name,
        iat=now,
        exp=now + expires_in,
    )
    header = _b64url_encode(_json_dumps({"alg": "HS256", "typ": "JWT"}))
    payload = _b64url_encode(_json_dumps(claims.model_dump(mode="json")))
    signature = _sign(f"{header}.{payload}".encode("ascii"))
    return f"{header}.{payload}.{signature}", expires_in


def _decode_access_token(token: str) -> AuthPrincipal:
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid bearer token")

    header_part, payload_part, signature_part = parts
    signed = f"{header_part}.{payload_part}".encode("ascii")
    expected_signature = _sign(signed)
    if not hmac.compare_digest(signature_part, expected_signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid bearer token")

    try:
        header = json.loads(_b64url_decode(header_part))
        if header.get("alg") != "HS256":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid bearer token")
        claims = AccessTokenClaims.model_validate(json.loads(_b64url_decode(payload_part)))
    except (ValueError, ValidationError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid bearer token") from exc

    if claims.exp <= int(time()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="expired bearer token")

    return AuthPrincipal(
        subject=claims.sub,
        role=claims.role,
        candidate_id=claims.candidate_id,
        display_name=claims.display_name,
        expires_at=claims.exp,
    )


def require_principal(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> AuthPrincipal:
    if credentials is None or not credentials.credentials.strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    return _decode_access_token(credentials.credentials)


def require_roles(*roles: AuthRole):
    allowed = set(roles)

    def _require_role(principal: AuthPrincipal = Depends(require_principal)) -> AuthPrincipal:
        if principal.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
        return principal

    return _require_role

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from apps.api.core.config import BACKEND_ROOT, settings


@dataclass(frozen=True)
class CandidateIdentity:
    email: str
    candidate_id: str
    display_name: str
    invite_token: str
    active: bool = True


def _resolve_registry_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (BACKEND_ROOT / path).resolve()


def _load_registry() -> dict[str, CandidateIdentity]:
    path = _resolve_registry_path(settings.candidate_registry_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("items") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise ValueError("candidate registry must be a JSON array or {'items': [...]}")

    identities: dict[str, CandidateIdentity] = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("candidate registry entries must be objects")
        email = str(item.get("email", "")).strip().lower()
        candidate_id = str(item.get("candidate_id", "")).strip()
        display_name = str(item.get("display_name", "")).strip()
        invite_token = str(item.get("invite_token", "")).strip()
        active = bool(item.get("active", True))
        if not email or not candidate_id or not display_name or not invite_token:
            raise ValueError("candidate registry entries require email, candidate_id, display_name, invite_token")
        identities[email] = CandidateIdentity(
            email=email,
            candidate_id=candidate_id,
            display_name=display_name,
            invite_token=invite_token,
            active=active,
        )
    return identities


def authenticate_candidate(email: str, invite_token: str) -> CandidateIdentity | None:
    normalized_email = email.strip().lower()
    normalized_token = invite_token.strip()
    if not normalized_email or not normalized_token:
        return None

    identity = _load_registry().get(normalized_email)
    if identity is None or not identity.active:
        return None
    if identity.invite_token != normalized_token:
        return None
    return identity

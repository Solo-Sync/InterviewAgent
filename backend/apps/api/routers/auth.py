from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from apps.api.core.auth import AuthRole, issue_access_token
from apps.api.core.candidates import authenticate_candidate
from apps.api.core.config import settings
from apps.api.core.response import ok

router = APIRouter(tags=["auth"])


class TokenIssueRequest(BaseModel):
    role: AuthRole
    email: str
    password: str | None = None
    candidate_id: str | None = None
    display_name: str | None = None


@router.post("/auth/token")
def issue_token(request: Request, body: TokenIssueRequest):
    if body.role == AuthRole.CANDIDATE:
        candidate = authenticate_candidate(body.email, body.password or "")
        if candidate is None:
            raise HTTPException(status_code=401, detail="invalid candidate credentials")
        requested_candidate_id = (body.candidate_id or "").strip()
        if requested_candidate_id and requested_candidate_id != candidate.candidate_id:
            raise HTTPException(status_code=403, detail="candidate_id override is forbidden")
        token, expires_in = issue_access_token(
            subject=candidate.email,
            role=AuthRole.CANDIDATE,
            candidate_id=candidate.candidate_id,
            display_name=candidate.display_name,
        )
        return ok(
            request,
            {
                "access_token": token,
                "token_type": "bearer",
                "expires_in": expires_in,
                "role": body.role.value,
                "candidate_id": candidate.candidate_id,
                "display_name": candidate.display_name,
            },
        )

    expected_email = settings.admin_login_email
    expected_password = settings.admin_login_password
    if body.role == AuthRole.ANNOTATOR:
        expected_email = settings.annotator_login_email
        expected_password = settings.annotator_login_password

    if body.email.strip().lower() != expected_email.strip().lower() or (body.password or "") != expected_password:
        raise HTTPException(status_code=401, detail="invalid credentials")

    token, expires_in = issue_access_token(
        subject=expected_email.strip().lower(),
        role=body.role,
        display_name=(body.display_name or "").strip() or None,
    )
    return ok(
        request,
        {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": expires_in,
            "role": body.role.value,
            "candidate_id": None,
            "display_name": (body.display_name or "").strip() or None,
        },
    )

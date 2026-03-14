from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from apps.api.core.auth import AuthRole, issue_access_token
from apps.api.core.candidates import authenticate_candidate, register_candidate
from apps.api.core.config import settings
from apps.api.core.response import ok
from libs.schemas.api import ApiResponseAuthToken, AuthTokenRequest, CandidateRegisterRequest

router = APIRouter(tags=["auth"])


@router.post("/auth/token", response_model=ApiResponseAuthToken)
def issue_token(request: Request, body: AuthTokenRequest):
    if body.role == AuthRole.CANDIDATE:
        username = (body.username or "").strip()
        if not username:
            raise HTTPException(status_code=400, detail="username is required for candidate login")
        candidate = authenticate_candidate(username, body.password)
        if candidate is None:
            raise HTTPException(status_code=401, detail="invalid candidate credentials")
        requested_candidate_id = (body.candidate_id or "").strip()
        if requested_candidate_id and requested_candidate_id != candidate.candidate_id:
            raise HTTPException(status_code=403, detail="candidate_id override is forbidden")
        token, expires_in = issue_access_token(
            subject=candidate.username,
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
                "role": body.role,
                "candidate_id": candidate.candidate_id,
                "display_name": candidate.display_name,
            },
        )

    requested_role = AuthRole(body.role)
    email = (body.email or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="email is required for non-candidate login")

    expected_email = settings.admin_login_email
    expected_password = settings.admin_login_password
    if requested_role == AuthRole.ANNOTATOR:
        expected_email = settings.annotator_login_email
        expected_password = settings.annotator_login_password

    if email != expected_email.strip().lower() or body.password != expected_password:
        raise HTTPException(status_code=401, detail="invalid credentials")

    token, expires_in = issue_access_token(
        subject=expected_email.strip().lower(),
        role=requested_role,
        display_name=(body.display_name or "").strip() or None,
    )
    return ok(
        request,
        {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": expires_in,
            "role": body.role,
            "candidate_id": None,
            "display_name": (body.display_name or "").strip() or None,
        },
    )


@router.post("/auth/register", response_model=ApiResponseAuthToken)
def register(request: Request, body: CandidateRegisterRequest):
    try:
        candidate = register_candidate(body.username, body.password)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="username already exists") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    token, expires_in = issue_access_token(
        subject=candidate.username,
        role=AuthRole.CANDIDATE,
        candidate_id=candidate.candidate_id,
        display_name=candidate.display_name,
    )
    return JSONResponse(
        status_code=201,
        content=ok(
            request,
            {
                "access_token": token,
                "token_type": "bearer",
                "expires_in": expires_in,
                "role": AuthRole.CANDIDATE.value,
                "candidate_id": candidate.candidate_id,
                "display_name": candidate.display_name,
            },
        ),
    )

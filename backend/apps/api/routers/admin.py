import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from apps.api.core.auth import AuthPrincipal, AuthRole, require_roles
from apps.api.core.dependencies import get_orchestrator
from apps.api.core.response import ok
from libs.schemas.api import (
    ApiResponseAdminSessionDetail,
    ApiResponseAdminSessionList,
    ApiResponseQuestionSetGet,
    ApiResponseQuestionSetList,
    ApiResponseRubricGet,
    ApiResponseRubricList,
)
from services.orchestrator.service import OrchestratorService

router = APIRouter(tags=["admin"])

BASE = Path(__file__).resolve().parents[3]
QUESTION_SET_DIR = BASE / "data" / "question_sets"
RUBRIC_DIR = BASE / "data" / "rubrics"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/admin/question_sets", response_model=ApiResponseQuestionSetList)
def list_question_sets(
    request: Request,
    _: AuthPrincipal = Depends(require_roles(AuthRole.ADMIN)),
):
    items = []
    for path in sorted(QUESTION_SET_DIR.glob("*.json")):
        payload = _load_json(path)
        items.append(
            {
                "question_set_id": payload.get("question_set_id"),
                "title": payload.get("title") or payload.get("name") or payload.get("question_set_id"),
                "description": payload.get("description"),
            }
        )
    return ok(request, {"items": items})


@router.get("/admin/question_sets/{question_set_id}", response_model=ApiResponseQuestionSetGet)
def get_question_set(
    request: Request,
    question_set_id: str,
    _: AuthPrincipal = Depends(require_roles(AuthRole.ADMIN)),
):
    path = QUESTION_SET_DIR / f"{question_set_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="question_set not found")
    payload = _load_json(path)
    question_set = {
        "question_set_id": payload.get("question_set_id"),
        "title": payload.get("title") or payload.get("name") or payload.get("question_set_id"),
        "description": payload.get("description"),
        "questions": payload.get("questions", []),
    }
    return ok(request, {"question_set": question_set})


@router.get("/admin/rubrics", response_model=ApiResponseRubricList)
def list_rubrics(
    request: Request,
    _: AuthPrincipal = Depends(require_roles(AuthRole.ADMIN)),
):
    items = []
    for path in sorted(RUBRIC_DIR.glob("*.json")):
        payload = _load_json(path)
        items.append(
            {
                "rubric_id": payload.get("rubric_id"),
                "title": payload.get("title") or payload.get("name") or payload.get("rubric_id"),
                "description": payload.get("description"),
            }
        )
    return ok(request, {"items": items})


@router.get("/admin/rubrics/{rubric_id}", response_model=ApiResponseRubricGet)
def get_rubric(
    request: Request,
    rubric_id: str,
    _: AuthPrincipal = Depends(require_roles(AuthRole.ADMIN)),
):
    path = RUBRIC_DIR / f"{rubric_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="rubric not found")
    payload = _load_json(path)
    rubric = {
        "rubric_id": payload.get("rubric_id"),
        "title": payload.get("title") or payload.get("name") or payload.get("rubric_id"),
        "description": payload.get("description"),
        "scale": payload.get("scale", {}),
    }
    return ok(request, {"rubric": rubric})


@router.get("/admin/sessions", response_model=ApiResponseAdminSessionList)
def list_sessions(
    request: Request,
    orchestrator: OrchestratorService = Depends(get_orchestrator),
    _: AuthPrincipal = Depends(require_roles(AuthRole.ADMIN)),
):
    items = []
    for session in orchestrator.list_sessions():
        report = orchestrator.get_report(session.session_id)
        review_status, prompt_injection_count, invalid_reason = orchestrator.get_session_review_status(
            session.session_id
        )
        items.append(
            {
                "session": session.model_dump(),
                "turn_count": orchestrator.count_turns(session.session_id),
                "report": report.model_dump() if report is not None else None,
                "review_status": review_status.value,
                "prompt_injection_count": prompt_injection_count,
                "invalid_reason": invalid_reason,
            }
        )
    return ok(request, {"items": items})


@router.get("/admin/sessions/{session_id}", response_model=ApiResponseAdminSessionDetail)
def get_session_detail(
    request: Request,
    session_id: str,
    orchestrator: OrchestratorService = Depends(get_orchestrator),
    _: AuthPrincipal = Depends(require_roles(AuthRole.ADMIN)),
):
    session = orchestrator.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    turns, _ = orchestrator.list_turns(session_id, limit=200, cursor=None)
    report = orchestrator.get_report(session_id)
    review_status, prompt_injection_count, invalid_reason = orchestrator.get_session_review_status(session_id)
    return ok(
        request,
        {
            "session": session.model_dump(),
            "turns": [turn.model_dump() for turn in turns],
            "report": report.model_dump() if report is not None else None,
            "opening_prompt": orchestrator.get_opening_prompt(session.question_set_id),
            "review_status": review_status.value,
            "prompt_injection_count": prompt_injection_count,
            "invalid_reason": invalid_reason,
        },
    )

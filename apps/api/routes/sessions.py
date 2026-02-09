from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from apps.api.dependencies import get_orchestrator
from apps.api.response import err_response, ok
from libs.schemas.api import SessionCreateRequest, SessionEndRequest, TurnCreateRequest
from services.orchestrator.service import CursorError, OrchestratorService

router = APIRouter(tags=["sessions"])


@router.post("/sessions")
def create_session(
    request: Request,
    body: SessionCreateRequest,
    orchestrator: OrchestratorService = Depends(get_orchestrator),
):
    session, next_action = orchestrator.create_session(body)
    return ok(request, {"session": session.model_dump(), "next_action": next_action.model_dump()})


@router.get("/sessions/{session_id}")
def get_session(
    request: Request,
    session_id: str,
    orchestrator: OrchestratorService = Depends(get_orchestrator),
):
    session = orchestrator.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    last_action = orchestrator.get_last_next_action(session_id)
    return ok(
        request,
        {
            "session": session.model_dump(),
            "last_next_action": last_action.model_dump() if last_action else None,
        },
    )


@router.post("/sessions/{session_id}/turns")
def create_turn(
    request: Request,
    session_id: str,
    body: TurnCreateRequest,
    orchestrator: OrchestratorService = Depends(get_orchestrator),
):
    try:
        turn, next_action = orchestrator.handle_turn(session_id, body)
    except KeyError:
        raise HTTPException(status_code=404, detail="session not found") from None
    except RuntimeError:
        raise HTTPException(status_code=409, detail="session already ended") from None

    return ok(
        request,
        {
            "turn": turn.model_dump(),
            "next_action": next_action.model_dump(),
            "triggers": turn.triggers,
            "scaffold": turn.scaffold.model_dump() if turn.scaffold else None,
            "evaluation": turn.evaluation.model_dump() if turn.evaluation else None,
        },
    )


@router.get("/sessions/{session_id}/turns")
def list_turns(
    request: Request,
    session_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
    orchestrator: OrchestratorService = Depends(get_orchestrator),
):
    session = orchestrator.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    try:
        items, next_cursor = orchestrator.list_turns(session_id, limit, cursor)
    except CursorError:
        return err_response(
            request,
            status_code=400,
            code="INVALID_ARGUMENT",
            message="invalid cursor",
            detail={"cursor": cursor},
        )

    return ok(
        request,
        {
            "items": [item.model_dump() for item in items],
            "next_cursor": next_cursor,
        },
    )


@router.post("/sessions/{session_id}/end")
def end_session(
    request: Request,
    session_id: str,
    body: SessionEndRequest,
    orchestrator: OrchestratorService = Depends(get_orchestrator),
):
    if orchestrator.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")
    report = orchestrator.end_session(session_id, body.reason.value)
    return ok(request, {"report": report.model_dump()})


@router.get("/sessions/{session_id}/report")
def get_report(
    request: Request,
    session_id: str,
    orchestrator: OrchestratorService = Depends(get_orchestrator),
):
    report = orchestrator.get_report(session_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    return ok(request, {"report": report.model_dump()})


@router.get("/sessions/{session_id}/events/export", response_class=PlainTextResponse)
def export_events(
    session_id: str,
    orchestrator: OrchestratorService = Depends(get_orchestrator),
):
    if orchestrator.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="session not found")
    return orchestrator.export_events(session_id)

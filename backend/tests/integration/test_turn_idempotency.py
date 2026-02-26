from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from apps.api.core.dependencies import orchestrator
from libs.schemas.api import SessionCreateRequest, TurnCreateRequest
from libs.schemas.base import Candidate, ClientMeta, SessionMode, TurnInput, TurnInputType


def test_handle_turn_idempotency_under_concurrency() -> None:
    session, _ = orchestrator.create_session(
        SessionCreateRequest(
            candidate=Candidate(candidate_id="stu_concurrency", display_name="Concurrent User"),
            mode=SessionMode.TEXT,
            question_set_id="qs_fermi_v1",
            scoring_policy_id="rubric_v1",
            scaffold_policy_id="scaffold_v1",
        )
    )
    req = TurnCreateRequest(
        input=TurnInput(type=TurnInputType.TEXT, text="我先列约束再估算"),
        client_meta=ClientMeta(client_timestamp=datetime(2026, 2, 21, 12, 0, tzinfo=timezone.utc)),
    )

    def _submit() -> str:
        turn, _ = orchestrator.handle_turn(session.session_id, req)
        return turn.turn_id

    with ThreadPoolExecutor(max_workers=2) as executor:
        turn_ids = list(executor.map(lambda _: _submit(), range(2)))

    assert turn_ids[0] == turn_ids[1]
    turns, _ = orchestrator.list_turns(session.session_id, limit=50, cursor=None)
    assert len(turns) == 1

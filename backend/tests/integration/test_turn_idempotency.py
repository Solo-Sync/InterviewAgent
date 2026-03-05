import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from apps.api.core.dependencies import orchestrator
from libs.schemas.api import SessionCreateRequest, TurnCreateRequest
from libs.schemas.base import Candidate, ClientMeta, SessionMode, TurnInput, TurnInputType
from libs.storage.postgres import SqlStore


def _build_orchestrators():
    database_url = os.environ["DATABASE_URL"]
    primary = type(orchestrator)()
    secondary = type(orchestrator)()
    primary.store = SqlStore(database_url)
    secondary.store = SqlStore(database_url)
    return primary, secondary


def _create_session(service, candidate_id: str):
    return service.create_session(
        SessionCreateRequest(
            candidate=Candidate(candidate_id=candidate_id, display_name="Concurrent User"),
            mode=SessionMode.TEXT,
            question_set_id="qs_fermi_v1",
            scoring_policy_id="rubric_v1",
            scaffold_policy_id="scaffold_v1",
        )
    )[0]


def test_handle_turn_idempotency_under_concurrency() -> None:
    primary, secondary = _build_orchestrators()
    session = _create_session(primary, "stu_concurrency")
    req = TurnCreateRequest(
        input=TurnInput(type=TurnInputType.TEXT, text="我先列约束再估算"),
        client_meta=ClientMeta(client_timestamp=datetime(2026, 2, 21, 12, 0, tzinfo=UTC)),
    )

    def _submit(service) -> str:
        turn, _ = service.handle_turn(session.session_id, req)
        return turn.turn_id

    with ThreadPoolExecutor(max_workers=2) as executor:
        turn_ids = list(executor.map(_submit, (primary, secondary)))

    assert turn_ids[0] == turn_ids[1]
    turns, _ = primary.list_turns(session.session_id, limit=50, cursor=None)
    assert len(turns) == 1


def test_handle_turn_assigns_distinct_indexes_under_concurrency() -> None:
    primary, secondary = _build_orchestrators()
    session = _create_session(primary, "stu_concurrency_indexes")
    requests = [
        TurnCreateRequest(
            input=TurnInput(type=TurnInputType.TEXT, text="第一回合：先拆分问题"),
            client_meta=ClientMeta(
                client_timestamp=datetime(2026, 2, 21, 12, 1, tzinfo=UTC),
            ),
        ),
        TurnCreateRequest(
            input=TurnInput(type=TurnInputType.TEXT, text="第二回合：补充假设"),
            client_meta=ClientMeta(
                client_timestamp=datetime(2026, 2, 21, 12, 2, tzinfo=UTC),
            ),
        ),
    ]

    def _submit(args: tuple[object, TurnCreateRequest]) -> tuple[str, int]:
        service, req = args
        turn, _ = service.handle_turn(session.session_id, req)
        return turn.turn_id, turn.turn_index

    with ThreadPoolExecutor(max_workers=2) as executor:
        created_turns = list(
            executor.map(_submit, ((primary, requests[0]), (secondary, requests[1])))
        )

    assert len({turn_id for turn_id, _ in created_turns}) == 2
    assert sorted(turn_index for _, turn_index in created_turns) == [0, 1]

    turns, _ = primary.list_turns(session.session_id, limit=50, cursor=None)
    assert [turn.turn_index for turn in turns] == [0, 1]

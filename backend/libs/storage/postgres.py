from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from sqlalchemy import JSON, TIMESTAMP, Column, Index, Integer, MetaData, String, Table, Text, UniqueConstraint
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from libs.schemas.base import NextAction, Report, Session as SessionModel, Turn


metadata = MetaData()
_UNSET = object()

sessions_table = Table(
    "sessions",
    metadata,
    Column("session_id", String, primary_key=True),
    Column("mode", String, nullable=False),
    Column("state", String, nullable=False, index=True),
    Column("question_set_id", String, nullable=False),
    Column("scoring_policy_id", String, nullable=False),
    Column("scaffold_policy_id", String, nullable=False),
    Column("candidate", JSON, nullable=True),
    Column("thresholds", JSON, nullable=True),
    Column("current_question_cursor", JSON, nullable=True),
    Column("theta", JSON, nullable=True),
    Column("last_next_action", JSON, nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    Column("ended_at", TIMESTAMP(timezone=True), nullable=True),
)

turns_table = Table(
    "turns",
    metadata,
    Column("turn_id", String, primary_key=True),
    Column("session_id", String, nullable=False, index=True),
    Column("turn_index", Integer, nullable=False),
    Column("state_before", String, nullable=False),
    Column("state_after", String, nullable=False),
    Column("idempotency_key", String, nullable=True),
    Column("turn_payload", JSON, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
    UniqueConstraint("session_id", "turn_index", name="uq_turn_session_index"),
    UniqueConstraint("session_id", "idempotency_key", name="uq_turn_session_idempotency"),
)

events_table = Table(
    "events",
    metadata,
    Column("event_id", String, primary_key=True),
    Column("session_id", String, nullable=False, index=True),
    Column("turn_id", String, nullable=True, index=True),
    Column("event_type", String, nullable=False, index=True),
    Column("payload", JSON, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
)

reports_table = Table(
    "reports",
    metadata,
    Column("session_id", String, primary_key=True),
    Column("report_payload", JSON, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
)

annotations_table = Table(
    "annotations",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("session_id", String, nullable=False, index=True),
    Column("turn_id", String, nullable=False),
    Column("human_scores", JSON, nullable=False),
    Column("notes", Text, nullable=True),
    Column("evidence", JSON, nullable=True),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False),
)

Index("idx_turns_session_created_at", turns_table.c.session_id, turns_table.c.created_at)
Index("idx_events_session_created_at", events_table.c.session_id, events_table.c.created_at)


class SqlStore:
    def __init__(self, database_url: str) -> None:
        backend_name = make_url(database_url).get_backend_name()
        if backend_name != "postgresql":
            raise ValueError("SqlStore requires a PostgreSQL DATABASE_URL")
        self.engine = create_engine(database_url, future=True, pool_pre_ping=True)

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        with Session(self.engine) as db:
            with db.begin():
                yield db

    def create_session(self, db: Session, session: SessionModel, next_action: NextAction) -> None:
        db.execute(
            sessions_table.insert().values(
                session_id=session.session_id,
                mode=session.mode.value,
                state=session.state.value,
                question_set_id=session.question_set_id,
                scoring_policy_id=session.scoring_policy_id,
                scaffold_policy_id=session.scaffold_policy_id,
                candidate=session.candidate.model_dump() if session.candidate else None,
                thresholds=session.thresholds.model_dump() if session.thresholds else None,
                current_question_cursor=(
                    session.current_question_cursor.model_dump(mode="json")
                    if session.current_question_cursor
                    else None
                ),
                theta=session.theta.model_dump(mode="json") if session.theta else None,
                last_next_action=next_action.model_dump(mode="json"),
                created_at=session.created_at,
                ended_at=None,
            )
        )

    def get_session(self, session_id: str) -> SessionModel | None:
        with Session(self.engine) as db:
            row = (
                db.execute(select(sessions_table).where(sessions_table.c.session_id == session_id))
                .mappings()
                .first()
            )
        return self._row_to_session(row)

    def list_sessions(self) -> list[SessionModel]:
        with Session(self.engine) as db:
            rows = (
                db.execute(select(sessions_table).order_by(sessions_table.c.created_at.desc()))
                .mappings()
                .all()
            )
        return [session for row in rows if (session := self._row_to_session(row)) is not None]

    def get_session_for_update(self, db: Session, session_id: str) -> SessionModel | None:
        query = select(sessions_table).where(sessions_table.c.session_id == session_id).with_for_update()
        row = db.execute(query).mappings().first()
        return self._row_to_session(row)

    def update_session(
        self,
        db: Session,
        session_id: str,
        *,
        state: str,
        last_next_action: NextAction | None = None,
        current_question_cursor: dict[str, Any] | None | object = _UNSET,
        theta: dict[str, Any] | None | object = _UNSET,
        ended_at: datetime | None = None,
    ) -> None:
        values: dict[str, Any] = {"state": state}
        if last_next_action is not None:
            values["last_next_action"] = last_next_action.model_dump(mode="json")
        if current_question_cursor is not _UNSET:
            values["current_question_cursor"] = current_question_cursor
        if theta is not _UNSET:
            values["theta"] = theta
        if ended_at is not None:
            values["ended_at"] = ended_at
        db.execute(sessions_table.update().where(sessions_table.c.session_id == session_id).values(**values))

    def get_last_next_action(self, session_id: str) -> NextAction | None:
        with Session(self.engine) as db:
            row = (
                db.execute(
                    select(sessions_table.c.last_next_action).where(sessions_table.c.session_id == session_id)
                )
                .mappings()
                .first()
            )
        if not row or not row["last_next_action"]:
            return None
        return NextAction.model_validate(row["last_next_action"])

    def get_next_turn_index(self, db: Session, session_id: str) -> int:
        latest = db.execute(
            select(func.max(turns_table.c.turn_index)).where(turns_table.c.session_id == session_id)
        ).scalar_one()
        if latest is None:
            return 0
        return int(latest) + 1

    def get_turn_by_idempotency(self, db: Session, session_id: str, idempotency_key: str) -> Turn | None:
        row = (
            db.execute(
                select(turns_table.c.turn_payload).where(
                    turns_table.c.session_id == session_id,
                    turns_table.c.idempotency_key == idempotency_key,
                )
            )
            .mappings()
            .first()
        )
        if not row:
            return None
        return Turn.model_validate(row["turn_payload"])

    def find_turn_by_idempotency(self, session_id: str, idempotency_key: str) -> Turn | None:
        with Session(self.engine) as db:
            return self.get_turn_by_idempotency(db, session_id, idempotency_key)

    def insert_turn(self, db: Session, session_id: str, turn: Turn, idempotency_key: str | None = None) -> None:
        db.execute(
            turns_table.insert().values(
                turn_id=turn.turn_id,
                session_id=session_id,
                turn_index=turn.turn_index,
                state_before=turn.state_before.value,
                state_after=turn.state_after.value,
                idempotency_key=idempotency_key,
                turn_payload=turn.model_dump(mode="json"),
                created_at=turn.created_at,
            )
        )

    def list_turns(self, session_id: str, limit: int, offset: int) -> list[Turn]:
        with Session(self.engine) as db:
            return self.list_turns_tx(db, session_id, offset=offset, limit=limit)

    def list_turns_tx(
        self,
        db: Session,
        session_id: str,
        *,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[Turn]:
        query = (
            select(turns_table.c.turn_payload)
            .where(turns_table.c.session_id == session_id)
            .order_by(turns_table.c.turn_index.asc())
            .offset(offset)
        )
        if limit is not None:
            query = query.limit(limit)
        rows = db.execute(query).mappings().all()
        return [Turn.model_validate(row["turn_payload"]) for row in rows]

    def list_recent_turns_tx(self, db: Session, session_id: str, limit: int) -> list[Turn]:
        rows = (
            db.execute(
                select(turns_table.c.turn_payload)
                .where(turns_table.c.session_id == session_id)
                .order_by(turns_table.c.turn_index.desc())
                .limit(limit)
            )
            .mappings()
            .all()
        )
        turns = [Turn.model_validate(row["turn_payload"]) for row in rows]
        turns.reverse()
        return turns

    def count_turns(self, session_id: str) -> int:
        with Session(self.engine) as db:
            count = db.execute(
                select(func.count()).select_from(turns_table).where(turns_table.c.session_id == session_id)
            ).scalar_one()
        return int(count)

    def get_latest_turn(self, db: Session, session_id: str) -> Turn | None:
        row = (
            db.execute(
                select(turns_table.c.turn_payload)
                .where(turns_table.c.session_id == session_id)
                .order_by(turns_table.c.turn_index.desc())
                .limit(1)
            )
            .mappings()
            .first()
        )
        if not row:
            return None
        return Turn.model_validate(row["turn_payload"])

    def turn_belongs_to_session(self, db: Session, session_id: str, turn_id: str) -> bool:
        row = (
            db.execute(
                select(turns_table.c.turn_id).where(
                    turns_table.c.session_id == session_id,
                    turns_table.c.turn_id == turn_id,
                )
            )
            .mappings()
            .first()
        )
        return row is not None

    def append_events(self, db: Session, events: list[dict[str, Any]]) -> None:
        if not events:
            return
        db.execute(events_table.insert(), events)

    def count_events_tx(self, db: Session, session_id: str, event_type: str) -> int:
        count = db.execute(
            select(func.count())
            .select_from(events_table)
            .where(events_table.c.session_id == session_id, events_table.c.event_type == event_type)
        ).scalar_one()
        return int(count)

    def list_events_tx(self, db: Session, session_id: str) -> list[dict[str, Any]]:
        rows = (
            db.execute(
                select(events_table)
                .where(events_table.c.session_id == session_id)
                .order_by(events_table.c.created_at.asc())
            )
            .mappings()
            .all()
        )
        return [
            {
                "event_id": row["event_id"],
                "session_id": row["session_id"],
                "turn_id": row["turn_id"],
                "event_type": row["event_type"],
                "payload": row["payload"],
                "ts": self._iso(row["created_at"]),
            }
            for row in rows
        ]

    def list_events(self, session_id: str) -> list[dict[str, Any]]:
        with Session(self.engine) as db:
            return self.list_events_tx(db, session_id)

    def upsert_report(self, db: Session, session_id: str, report: Report) -> None:
        now = datetime.now(timezone.utc)
        exists = (
            db.execute(select(reports_table.c.session_id).where(reports_table.c.session_id == session_id))
            .mappings()
            .first()
        )
        if exists:
            db.execute(
                reports_table.update()
                .where(reports_table.c.session_id == session_id)
                .values(report_payload=report.model_dump(mode="json"), created_at=now)
            )
            return
        db.execute(
            reports_table.insert().values(
                session_id=session_id,
                report_payload=report.model_dump(mode="json"),
                created_at=now,
            )
        )

    def get_report(self, session_id: str) -> Report | None:
        with Session(self.engine) as db:
            row = (
                db.execute(
                    select(reports_table.c.report_payload).where(reports_table.c.session_id == session_id)
                )
                .mappings()
                .first()
            )
        if not row:
            return None
        return Report.model_validate(row["report_payload"])

    def create_annotation(
        self,
        db: Session,
        *,
        session_id: str,
        turn_id: str,
        human_scores: dict[str, Any],
        notes: str | None,
        evidence: list[dict[str, Any]] | None,
    ) -> None:
        db.execute(
            annotations_table.insert().values(
                session_id=session_id,
                turn_id=turn_id,
                human_scores=human_scores,
                notes=notes,
                evidence=evidence,
                created_at=datetime.now(timezone.utc),
            )
        )

    def _row_to_session(self, row: dict[str, Any] | None) -> SessionModel | None:
        if row is None:
            return None
        payload = {
            "session_id": row["session_id"],
            "candidate": row["candidate"],
            "mode": row["mode"],
            "state": row["state"],
            "question_set_id": row["question_set_id"],
            "scoring_policy_id": row["scoring_policy_id"],
            "scaffold_policy_id": row["scaffold_policy_id"],
            "thresholds": row["thresholds"],
            "current_question_cursor": row.get("current_question_cursor"),
            "theta": row.get("theta"),
            "created_at": row["created_at"],
        }
        return SessionModel.model_validate(payload)

    def _iso(self, dt: datetime | str) -> str:
        if isinstance(dt, str):
            return dt
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc).isoformat()
        return dt.isoformat()

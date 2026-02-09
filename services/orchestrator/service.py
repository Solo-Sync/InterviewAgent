import base64
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from libs.schemas.api import CursorEnvelope, SessionCreateRequest, TurnCreateRequest
from libs.schemas.base import (
    DimScores,
    NextAction,
    NextActionType,
    PreprocessResult,
    Report,
    ReportPoint,
    ScaffoldLevel,
    Session,
    SessionState,
    Turn,
)
from services.evaluation.aggregator import ScoreAggregator
from services.nlp.preprocess import Preprocessor
from services.orchestrator.policy import OrchestratorPolicy
from services.orchestrator.selector import QuestionSelector
from services.orchestrator.state_machine import SessionStateMachine
from services.safety.classifier import SafetyClassifier
from services.scaffold.generator import ScaffoldGenerator
from services.trigger.detector import TriggerDetector


@dataclass
class InMemoryStore:
    sessions: dict[str, Session] = field(default_factory=dict)
    turns: dict[str, list[Turn]] = field(default_factory=dict)
    reports: dict[str, Report] = field(default_factory=dict)
    last_next_actions: dict[str, NextAction] = field(default_factory=dict)


class CursorError(ValueError):
    pass


class OrchestratorService:
    def __init__(self) -> None:
        self.store = InMemoryStore()
        self.state_machine = SessionStateMachine()
        self.policy = OrchestratorPolicy()
        self.selector = QuestionSelector()
        self.preprocessor = Preprocessor()
        self.safety = SafetyClassifier()
        self.trigger_detector = TriggerDetector()
        self.scaffold = ScaffoldGenerator()
        self.scoring = ScoreAggregator()

    def create_session(self, req: SessionCreateRequest) -> tuple[Session, NextAction]:
        session = Session(
            session_id=f"sess_{uuid4().hex[:12]}",
            candidate=req.candidate,
            mode=req.mode,
            state=SessionState.S_INIT,
            question_set_id=req.question_set_id,
            scoring_policy_id=req.scoring_policy_id,
            scaffold_policy_id=req.scaffold_policy_id,
            thresholds=req.thresholds,
            created_at=datetime.now(timezone.utc),
        )
        self.store.sessions[session.session_id] = session
        self.store.turns[session.session_id] = []
        next_action = NextAction(
            type=NextActionType.ASK,
            text=self.selector.next_prompt(session.session_id, 0),
            level=None,
            payload=None,
        )
        self.store.last_next_actions[session.session_id] = next_action
        return session, next_action

    def get_session(self, session_id: str) -> Session | None:
        return self.store.sessions.get(session_id)

    def get_last_next_action(self, session_id: str) -> NextAction | None:
        return self.store.last_next_actions.get(session_id)

    def handle_turn(self, session_id: str, req: TurnCreateRequest) -> tuple[Turn, NextAction]:
        session = self.store.sessions.get(session_id)
        if session is None:
            raise KeyError("session not found")
        if session.state == SessionState.S_END:
            raise RuntimeError("session already ended")

        before = session.state
        raw_text = req.input.text or ""
        preprocess = PreprocessResult(**self.preprocessor.run(raw_text))
        safety = self.safety.check(preprocess.clean_text)

        if not safety["is_safe"] and safety["action"] == "BLOCK":
            next_action = NextAction(type=NextActionType.END, text="Session ended by safety policy.")
            after = self.state_machine.next_state(before, next_action.type)
            session.state = after
            eval_result = self.scoring.score("")
            turn = self._build_turn(
                turn_index=len(self.store.turns[session_id]),
                req=req,
                state_before=before,
                state_after=after,
                preprocess=preprocess,
                triggers=None,
                evaluation=eval_result,
                next_action=next_action,
                scaffold=None,
            )
            self.store.turns[session_id].append(turn)
            self.store.last_next_actions[session_id] = next_action
            return turn, next_action

        clean_text = safety["sanitized_text"] or preprocess.clean_text
        triggers = self.trigger_detector.detect(clean_text)
        action_type, scaffold_level = self.policy.choose_action({t.type for t in triggers})
        scaffold = self.scaffold.generate(scaffold_level, {"text": clean_text}) if scaffold_level else None

        action_text = (
            scaffold.prompt
            if scaffold and scaffold.fired and scaffold.prompt
            else self.selector.next_prompt(session_id, len(self.store.turns[session_id]) + 1)
        )

        next_action = NextAction(type=action_type, text=action_text, level=scaffold_level, payload=None)
        eval_result = self.scoring.score(clean_text)
        after = self.state_machine.next_state(before, next_action.type)
        session.state = after

        turn = self._build_turn(
            turn_index=len(self.store.turns[session_id]),
            req=req,
            state_before=before,
            state_after=after,
            preprocess=preprocess,
            triggers=triggers or None,
            evaluation=eval_result,
            next_action=next_action,
            scaffold=scaffold,
        )
        self.store.turns[session_id].append(turn)
        self.store.last_next_actions[session_id] = next_action
        return turn, next_action

    def list_turns(self, session_id: str, limit: int, cursor: str | None) -> tuple[list[Turn], str | None]:
        turns = self.store.turns.get(session_id, [])
        start = self._decode_cursor(cursor)
        if start < 0 or start > len(turns):
            raise CursorError("invalid cursor")

        end = min(start + limit, len(turns))
        next_cursor = self._encode_cursor(end) if end < len(turns) else None
        return turns[start:end], next_cursor

    def end_session(self, session_id: str, reason: str) -> Report:
        turns = self.store.turns.get(session_id, [])
        if turns and turns[-1].evaluation is not None:
            latest = turns[-1].evaluation.scores
        else:
            latest = DimScores(plan=0.0, monitor=0.0, evaluate=0.0, adapt=0.0)
        timeline = [
            ReportPoint(
                turn_index=t.turn_index,
                scores=t.evaluation.scores if t.evaluation else latest,
            )
            for t in turns
        ]
        report = Report(overall=latest, timeline=timeline, notes=[f"ended:{reason}"])
        self.store.reports[session_id] = report
        session = self.store.sessions.get(session_id)
        if session is not None:
            session.state = SessionState.S_END
        return report

    def get_report(self, session_id: str) -> Report | None:
        return self.store.reports.get(session_id)

    def export_events(self, session_id: str) -> str:
        turns = self.store.turns.get(session_id, [])
        lines = []
        for turn in turns:
            lines.append(
                json.dumps(
                    {
                        "event_id": f"evt_{uuid4().hex[:12]}",
                        "session_id": session_id,
                        "turn_id": turn.turn_id,
                        "event_type": "evaluation_completed",
                        "payload": turn.evaluation.model_dump() if turn.evaluation else {},
                        "ts": turn.created_at.isoformat(),
                    },
                    ensure_ascii=False,
                )
            )
        return "\n".join(lines)

    def _build_turn(
        self,
        turn_index: int,
        req: TurnCreateRequest,
        state_before: SessionState,
        state_after: SessionState,
        preprocess: PreprocessResult,
        triggers,
        evaluation,
        next_action,
        scaffold,
    ) -> Turn:
        turn_id = f"turn_{uuid4().hex[:12]}"
        return Turn(
            turn_id=turn_id,
            turn_index=turn_index,
            input=req.input,
            preprocess=preprocess,
            triggers=triggers,
            scaffold=scaffold,
            evaluation=evaluation,
            next_action=next_action,
            state_before=state_before,
            state_after=state_after,
            created_at=datetime.now(timezone.utc),
        )

    def _encode_cursor(self, offset: int) -> str:
        envelope = CursorEnvelope(offset=offset, ts=datetime.now(timezone.utc))
        raw = envelope.model_dump_json().encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii")

    def _decode_cursor(self, cursor: str | None) -> int:
        if cursor is None:
            return 0
        try:
            decoded = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
            payload = CursorEnvelope.model_validate_json(decoded)
            return payload.offset
        except Exception as exc:  # noqa: BLE001
            raise CursorError("invalid cursor") from exc

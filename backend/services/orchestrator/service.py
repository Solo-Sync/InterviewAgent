from __future__ import annotations

import base64
import hashlib
import json
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from apps.api.core.config import settings
from libs.schemas.api import CursorEnvelope, HumanAnnotationCreateRequest, SessionCreateRequest, TurnCreateRequest
from libs.schemas.base import (
    AsrResult,
    DimScores,
    NextAction,
    NextActionType,
    PreprocessResult,
    Report,
    ReportPoint,
    Session,
    SessionState,
    Turn,
    TurnInputType,
)
from libs.storage.files import FileStore
from libs.storage.postgres import SqlStore
from services.asr import ASRService
from services.evaluation.aggregator import ScoreAggregator
from services.nlp.preprocess import Preprocessor
from services.orchestrator.policy import OrchestratorPolicy
from services.orchestrator.selector import QuestionSelector
from services.orchestrator.state_machine import SessionStateMachine
from services.safety.classifier import SafetyClassifier
from services.scaffold.generator import ScaffoldGenerator
from services.trigger.detector import TriggerDetector


class CursorError(ValueError):
    pass


class SessionLockPool:
    def __init__(self) -> None:
        self._locks: dict[str, threading.RLock] = {}
        self._guard = threading.Lock()

    @contextmanager
    def hold(self, session_id: str):
        with self._guard:
            lock = self._locks.get(session_id)
            if lock is None:
                lock = threading.RLock()
                self._locks[session_id] = lock
        with lock:
            yield


class OrchestratorService:
    def __init__(self) -> None:
        self.state_machine = SessionStateMachine()
        self.policy = OrchestratorPolicy()
        self.selector = QuestionSelector()
        self.preprocessor = Preprocessor()
        self.safety = SafetyClassifier()
        self.trigger_detector = TriggerDetector()
        self.scaffold = ScaffoldGenerator()
        self.scoring = ScoreAggregator()
        self.asr_service = ASRService()
        self.file_store = FileStore()
        self.store = SqlStore(settings.database_url)
        self.session_locks = SessionLockPool()

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
        next_action = NextAction(
            type=NextActionType.ASK,
            text=self.selector.next_prompt(session.session_id, 0),
            level=None,
            payload=None,
        )
        with self.store.transaction() as db:
            self.store.create_session(db, session, next_action)
            self.store.append_events(
                db,
                [
                    self._event(
                        session.session_id,
                        None,
                        "session_created",
                        {
                            "candidate_id": session.candidate.candidate_id if session.candidate else None,
                            "mode": session.mode.value,
                        },
                    )
                ],
            )
        return session, next_action

    def get_session(self, session_id: str) -> Session | None:
        return self.store.get_session(session_id)

    def get_last_next_action(self, session_id: str) -> NextAction | None:
        return self.store.get_last_next_action(session_id)

    def handle_turn(self, session_id: str, req: TurnCreateRequest) -> tuple[Turn, NextAction]:
        with self.session_locks.hold(session_id):
            with self.store.transaction() as db:
                session = self.store.get_session_for_update(db, session_id)
                if session is None:
                    raise KeyError("session not found")
                if session.state == SessionState.S_END:
                    raise RuntimeError("session already ended")

                idempotency_key = self._build_idempotency_key(session_id, req)
                if idempotency_key:
                    existing_turn = self.store.get_turn_by_idempotency(db, session_id, idempotency_key)
                    if existing_turn is not None:
                        next_action = existing_turn.next_action or self.store.get_last_next_action(session_id)
                        if next_action is None:
                            next_action = NextAction(type=NextActionType.WAIT, text="Please continue.")
                        return existing_turn, next_action

                turn_index = self.store.get_next_turn_index(db, session_id)
                before = session.state
                events = [self._event(session_id, None, "turn_received", req.model_dump(mode="json"))]

                raw_text, asr_result = self._resolve_text_and_asr(req)
                if asr_result is not None:
                    events.append(
                        self._event(
                            session_id,
                            None,
                            "asr_completed",
                            asr_result.model_dump(mode="json"),
                        )
                    )

                preprocess = PreprocessResult(**self.preprocessor.run(raw_text))
                events.append(
                    self._event(
                        session_id,
                        None,
                        "preprocess_completed",
                        preprocess.model_dump(mode="json"),
                    )
                )
                safety = self.safety.check(preprocess.clean_text)

                if not safety["is_safe"] and safety["action"] == "BLOCK":
                    next_action = NextAction(type=NextActionType.END, text="Session ended by safety policy.")
                    after = self.state_machine.next_state(before, next_action.type)
                    eval_result = self.scoring.score("")
                    turn = self._build_turn(
                        turn_index=turn_index,
                        req=req,
                        state_before=before,
                        state_after=after,
                        asr=asr_result,
                        preprocess=preprocess,
                        triggers=None,
                        evaluation=eval_result,
                        next_action=next_action,
                        scaffold=None,
                    )
                    self.store.insert_turn(db, session_id, turn, idempotency_key=idempotency_key)
                    self.store.update_session(
                        db,
                        session_id,
                        state=after.value,
                        last_next_action=next_action,
                        ended_at=datetime.now(timezone.utc),
                    )
                    events.extend(
                        [
                            self._event(
                                session_id,
                                turn.turn_id,
                                "safety_blocked",
                                {
                                    "category": safety.get("category"),
                                    "action": safety.get("action"),
                                },
                            ),
                            self._event(
                                session_id,
                                turn.turn_id,
                                "evaluation_completed",
                                eval_result.model_dump(mode="json"),
                            ),
                            self._event(
                                session_id,
                                turn.turn_id,
                                "next_action_decided",
                                next_action.model_dump(mode="json"),
                            ),
                        ]
                    )
                    self.store.append_events(db, events)
                    return turn, next_action

                clean_text = safety["sanitized_text"] or preprocess.clean_text
                if safety["action"] == "SANITIZE":
                    events.append(
                        self._event(
                            session_id,
                            None,
                            "safety_sanitized",
                            {
                                "category": safety.get("category"),
                                "action": safety.get("action"),
                                "sanitized_text": clean_text,
                            },
                        )
                    )

                triggers = self.trigger_detector.detect(clean_text)
                for trigger in triggers:
                    events.append(
                        self._event(
                            session_id,
                            None,
                            "trigger_detected",
                            trigger.model_dump(mode="json"),
                        )
                    )

                action_type, scaffold_level = self.policy.choose_action({t.type for t in triggers})
                scaffold = self.scaffold.generate(scaffold_level, {"text": clean_text}) if scaffold_level else None
                if scaffold and scaffold.fired:
                    events.append(
                        self._event(
                            session_id,
                            None,
                            "scaffold_fired",
                            scaffold.model_dump(mode="json"),
                        )
                    )

                action_text = (
                    scaffold.prompt
                    if scaffold and scaffold.fired and scaffold.prompt
                    else self.selector.next_prompt(session_id, turn_index + 1)
                )
                next_action = NextAction(type=action_type, text=action_text, level=scaffold_level, payload=None)
                eval_result = self.scoring.score(clean_text)
                after = self.state_machine.next_state(before, next_action.type)

                turn = self._build_turn(
                    turn_index=turn_index,
                    req=req,
                    state_before=before,
                    state_after=after,
                    asr=asr_result,
                    preprocess=preprocess,
                    triggers=triggers or None,
                    evaluation=eval_result,
                    next_action=next_action,
                    scaffold=scaffold,
                )
                self.store.insert_turn(db, session_id, turn, idempotency_key=idempotency_key)
                self.store.update_session(db, session_id, state=after.value, last_next_action=next_action)
                events.extend(
                    [
                        self._event(
                            session_id,
                            turn.turn_id,
                            "evaluation_completed",
                            eval_result.model_dump(mode="json"),
                        ),
                        self._event(
                            session_id,
                            turn.turn_id,
                            "next_action_decided",
                            next_action.model_dump(mode="json"),
                        ),
                    ]
                )
                self.store.append_events(db, events)
                return turn, next_action

    def list_turns(self, session_id: str, limit: int, cursor: str | None) -> tuple[list[Turn], str | None]:
        total = self.store.count_turns(session_id)
        start = self._decode_cursor(cursor)
        if start < 0 or start > total:
            raise CursorError("invalid cursor")

        items = self.store.list_turns(session_id, limit, start)
        end = start + len(items)
        next_cursor = self._encode_cursor(end) if end < total else None
        return items, next_cursor

    def end_session(self, session_id: str, reason: str) -> Report:
        with self.session_locks.hold(session_id):
            with self.store.transaction() as db:
                session = self.store.get_session_for_update(db, session_id)
                if session is None:
                    raise KeyError("session not found")

                turns = self.store.list_turns_tx(db, session_id)
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
                self.store.upsert_report(db, session_id, report)
                end_action = NextAction(type=NextActionType.END, text="Session closed.")
                self.store.update_session(
                    db,
                    session_id,
                    state=SessionState.S_END.value,
                    last_next_action=end_action,
                    ended_at=datetime.now(timezone.utc),
                )
                self.store.append_events(
                    db,
                    [self._event(session_id, None, "session_ended", {"reason": reason})],
                )
                return report

    def get_report(self, session_id: str) -> Report | None:
        return self.store.get_report(session_id)

    def export_events(self, session_id: str) -> str:
        lines = []
        for event in self.store.list_events(session_id):
            lines.append(json.dumps(event, ensure_ascii=False))
        return "\n".join(lines)

    def create_annotation(self, session_id: str, body: HumanAnnotationCreateRequest) -> None:
        with self.store.transaction() as db:
            session = self.store.get_session_for_update(db, session_id)
            if session is None:
                raise KeyError("session not found")
            self.store.create_annotation(
                db,
                session_id=session_id,
                turn_id=body.turn_id,
                human_scores=body.human_scores.model_dump(mode="json"),
                notes=body.notes,
                evidence=[e.model_dump(mode="json") for e in body.evidence] if body.evidence else None,
            )
            self.store.append_events(
                db,
                [
                    self._event(
                        session_id,
                        body.turn_id,
                        "annotation_created",
                        {"notes": body.notes, "has_evidence": bool(body.evidence)},
                    )
                ],
            )

    def _build_turn(
        self,
        turn_index: int,
        req: TurnCreateRequest,
        state_before: SessionState,
        state_after: SessionState,
        asr: AsrResult | None,
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
            asr=asr,
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

    def _resolve_text_and_asr(self, req: TurnCreateRequest) -> tuple[str, AsrResult | None]:
        if req.input.type == TurnInputType.TEXT:
            return req.input.text or "", None

        audio_bytes, filename = self._resolve_audio_bytes(req)
        asr = self.asr_service.transcribe(
            audio_bytes=audio_bytes,
            filename=filename,
            language="zh",
            need_word_timestamps=True,
        )
        return asr.raw_text, asr

    def _resolve_audio_bytes(self, req: TurnCreateRequest) -> tuple[bytes, str]:
        if req.input.audio_id:
            path = self.file_store.path_for(req.input.audio_id)
            if not path.exists() or not path.is_file():
                raise ValueError("audio_id not found")
            return path.read_bytes(), path.name

        if not req.input.audio_url:
            raise ValueError("audio_ref requires audio_url or audio_id")

        url = req.input.audio_url
        if url.startswith("data:"):
            return self._decode_data_url(url)

        if url.startswith("http://") or url.startswith("https://"):
            import httpx

            with httpx.Client(timeout=20.0) as client:
                resp = client.get(url)
                resp.raise_for_status()
                return resp.content, url.rsplit("/", 1)[-1] or "audio.bin"

        raise ValueError("unsupported audio_url scheme")

    def _decode_data_url(self, data_url: str) -> tuple[bytes, str]:
        try:
            header, payload = data_url.split(",", 1)
        except ValueError as exc:
            raise ValueError("invalid data url") from exc

        if ";base64" not in header:
            raise ValueError("data url must be base64 encoded")

        mime = header[5:].split(";")[0] if header.startswith("data:") else "application/octet-stream"
        ext = "wav"
        if "/" in mime:
            ext = mime.split("/", 1)[1] or ext

        try:
            data = base64.b64decode(payload, validate=True)
        except Exception as exc:  # noqa: BLE001
            raise ValueError("invalid base64 audio payload") from exc

        return data, f"upload.{ext}"

    def _build_idempotency_key(self, session_id: str, req: TurnCreateRequest) -> str | None:
        meta = req.client_meta
        if meta is None or meta.client_timestamp is None:
            return None

        ts = meta.client_timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = ts.astimezone(timezone.utc)

        if req.input.type == TurnInputType.TEXT:
            material = req.input.text or ""
        else:
            material = req.input.audio_id or req.input.audio_url or ""
        raw = f"{session_id}|{ts.isoformat()}|{req.input.type.value}|{material}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _event(
        self,
        session_id: str,
        turn_id: str | None,
        event_type: str,
        payload: dict,
    ) -> dict:
        return {
            "event_id": f"evt_{uuid4().hex[:12]}",
            "session_id": session_id,
            "turn_id": turn_id,
            "event_type": event_type,
            "payload": payload,
            "created_at": datetime.now(timezone.utc),
        }

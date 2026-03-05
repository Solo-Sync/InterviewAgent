from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import logging
import socket
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from urllib.parse import urlparse
from uuid import uuid4

from apps.api.core.config import settings
from libs.observability import log_event, observe_turn_stage, observe_turn_total
from libs.schemas.api import CursorEnvelope, HumanAnnotationCreateRequest, SessionCreateRequest, TurnCreateRequest
from libs.schemas.base import (
    AsrResult,
    DimScores,
    NextAction,
    NextActionType,
    PreprocessResult,
    QuestionCursor,
    QuestionRef,
    Report,
    ReportPoint,
    Session,
    SessionState,
    Turn,
    TurnInputType,
)
from libs.storage.files import FileStore
from libs.storage.postgres import SqlStore
from sqlalchemy.exc import IntegrityError
from services.asr import ASRService
from services.evaluation.aggregator import ScoreAggregator
from services.evaluation.session_scorer import SessionScorer
from services.nlp.preprocess import Preprocessor
from services.orchestrator.policy import OrchestratorPolicy
from services.orchestrator.selector import QuestionSelector
from services.orchestrator.state_machine import SessionStateMachine
from services.safety.classifier import SafetyClassifier
from services.scaffold.generator import ScaffoldGenerator
from services.trigger.detector import TriggerDetector

logger = logging.getLogger(__name__)


class CursorError(ValueError):
    pass


class OrchestratorService:
    def __init__(self) -> None:
        self.state_machine = SessionStateMachine()
        self.policy = OrchestratorPolicy()
        self.selector = QuestionSelector()
        self.preprocessor = Preprocessor()
        self.safety = SafetyClassifier()
        self.trigger_detector = TriggerDetector()
        self.scaffold = ScaffoldGenerator()
        self.scoring = ScoreAggregator(judge_mode="turn_aux")
        self.session_scoring = SessionScorer()
        self.asr_service = ASRService()
        self.file_store = FileStore()
        self.store = SqlStore(settings.database_url)
        self.question_set_dir = Path(__file__).resolve().parents[2] / "data" / "question_sets"
        self.rubric_dir = Path(__file__).resolve().parents[2] / "data" / "rubrics"

    def create_session(self, req: SessionCreateRequest) -> tuple[Session, NextAction]:
        self._ensure_session_refs_exist(req.question_set_id, req.scoring_policy_id)
        opening = self.selector.opening_selection(req.question_set_id)
        session = Session(
            session_id=f"sess_{uuid4().hex[:12]}",
            candidate=req.candidate,
            mode=req.mode,
            state=SessionState.S_INIT,
            question_set_id=req.question_set_id,
            scoring_policy_id=req.scoring_policy_id,
            scaffold_policy_id=req.scaffold_policy_id,
            thresholds=req.thresholds,
            current_question_cursor=opening.cursor,
            created_at=datetime.now(timezone.utc),
        )
        next_action = NextAction(
            type=opening.action_type,
            text=opening.question.text if opening.question else None,
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
        log_event(
            logger,
            logging.INFO,
            "session_created",
            session_id=session.session_id,
            candidate_id=session.candidate.candidate_id if session.candidate else None,
        )
        return session, next_action

    def get_session(self, session_id: str) -> Session | None:
        return self.store.get_session(session_id)

    def list_sessions(self) -> list[Session]:
        return self.store.list_sessions()

    def get_last_next_action(self, session_id: str) -> NextAction | None:
        return self.store.get_last_next_action(session_id)

    def count_turns(self, session_id: str) -> int:
        return self.store.count_turns(session_id)

    def handle_turn(self, session_id: str, req: TurnCreateRequest) -> tuple[Turn, NextAction]:
        idempotency_key = self._build_idempotency_key(session_id, req)
        last_conflict: IntegrityError | None = None
        for _ in range(3):
            try:
                return self._handle_turn_once(session_id, req, idempotency_key)
            except IntegrityError as exc:
                recovered = self._recover_turn_conflict(session_id, idempotency_key, exc)
                if recovered is not None:
                    return recovered
                if not (self._is_turn_index_conflict(exc) or self._is_idempotency_conflict(exc)):
                    raise
                last_conflict = exc
        if last_conflict is not None:
            raise last_conflict
        raise AssertionError("unreachable")

    def _handle_turn_once(
        self,
        session_id: str,
        req: TurnCreateRequest,
        idempotency_key: str | None,
    ) -> tuple[Turn, NextAction]:
        turn_started = perf_counter()
        with self.store.transaction() as db:
            session = self.store.get_session_for_update(db, session_id)
            if session is None:
                raise KeyError("session not found")
            if session.state == SessionState.S_END:
                raise RuntimeError("session already ended")

            if idempotency_key:
                existing_turn = self.store.get_turn_by_idempotency(db, session_id, idempotency_key)
                if existing_turn is not None:
                    return existing_turn, self._resolve_existing_next_action(session_id, existing_turn)

            turn_index = self.store.get_next_turn_index(db, session_id)
            turn_id = f"turn_{uuid4().hex[:12]}"
            before = session.state
            current_cursor = session.current_question_cursor
            current_question = self._question_from_cursor(current_cursor)
            events = [self._event(session_id, None, "turn_received", req.model_dump(mode="json"))]
            log_event(
                logger,
                logging.INFO,
                "turn_pipeline_started",
                session_id=session_id,
                turn_id=turn_id,
                turn_index=turn_index,
                state_before=before.value,
                input_type=req.input.type.value,
                input_text=req.input.text if req.input.type == TurnInputType.TEXT else None,
                input_audio_id=req.input.audio_id,
                input_audio_url=req.input.audio_url,
                idempotency_key=idempotency_key,
            )

            asr_started = perf_counter()
            raw_text, asr_result = self._resolve_text_and_asr(req)
            self._record_turn_stage("asr", asr_started, session_id=session_id, turn_id=turn_id)
            if asr_result is not None:
                events.append(
                    self._event(
                        session_id,
                        None,
                        "asr_completed",
                        asr_result.model_dump(mode="json"),
                    )
                )
            log_event(
                logger,
                logging.INFO,
                "turn_input_resolved",
                session_id=session_id,
                turn_id=turn_id,
                raw_text=raw_text,
                asr=asr_result.model_dump(mode="json") if asr_result else None,
            )

            preprocess_started = perf_counter()
            preprocess = PreprocessResult(**self.preprocessor.run(raw_text))
            self._record_turn_stage("preprocess", preprocess_started, session_id=session_id, turn_id=turn_id)
            events.append(
                self._event(
                    session_id,
                    None,
                    "preprocess_completed",
                    preprocess.model_dump(mode="json"),
                )
            )
            safety_started = perf_counter()
            safety = self.safety.check(preprocess.clean_text)
            self._record_turn_stage("safety", safety_started, session_id=session_id, turn_id=turn_id)
            log_event(
                logger,
                logging.INFO,
                "turn_safety_evaluated",
                session_id=session_id,
                turn_id=turn_id,
                raw_text=raw_text,
                preprocess=preprocess.model_dump(mode="json"),
                safety=safety,
            )

            if not safety["is_safe"] and safety["action"] == "BLOCK":
                next_action = NextAction(type=NextActionType.END, text="Session ended by safety policy.")
                after = self.state_machine.next_state(before, next_action.type)
                turn = self._build_turn(
                    turn_id=turn_id,
                    turn_index=turn_index,
                    req=req,
                    question=current_question,
                    state_before=before,
                    state_after=after,
                    asr=asr_result,
                    preprocess=preprocess,
                    triggers=None,
                    evaluation=None,
                    next_action=next_action,
                    scaffold=None,
                )
                self.store.insert_turn(db, session_id, turn, idempotency_key=idempotency_key)
                self.store.update_session(
                    db,
                    session_id,
                    state=after.value,
                    last_next_action=next_action,
                    current_question_cursor=None,
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
                            "next_action_decided",
                            next_action.model_dump(mode="json"),
                        ),
                    ]
                )
                self.store.append_events(db, events)
                self._record_turn_total(
                    turn_started,
                    session_id=session_id,
                    turn_id=turn.turn_id,
                    state_before=before.value,
                    state_after=after.value,
                    next_action=next_action.type.value,
                )
                log_event(
                    logger,
                    logging.WARNING,
                    "next_action_decision_logged",
                    session_id=session_id,
                    turn_id=turn_id,
                    decision_source="safety_block",
                    decision_reasons={
                        "category": safety.get("category"),
                        "action": safety.get("action"),
                    },
                    next_action=next_action.model_dump(mode="json"),
                    state_before=before.value,
                    state_after=after.value,
                )
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

            silence_s = self._extract_silence_seconds(asr_result)
            silence_threshold = session.thresholds.silence_s if session.thresholds else 15.0
            loop_threshold = session.thresholds.loop_threshold if session.thresholds else 0.8
            recent_turns = self.store.list_recent_turns_tx(db, session_id, limit=2)
            recent_texts = [
                turn.preprocess.clean_text
                if turn.preprocess and turn.preprocess.clean_text
                else str(turn.input.text or "")
                for turn in recent_turns
            ]
            trigger_started = perf_counter()
            triggers = self.trigger_detector.detect(
                clean_text,
                recent_texts=recent_texts,
                silence_s=silence_s,
                silence_threshold_s=silence_threshold,
                loop_threshold=loop_threshold,
            )
            self._record_turn_stage("trigger", trigger_started, session_id=session_id, turn_id=turn_id)
            for trigger in triggers:
                events.append(
                    self._event(
                        session_id,
                        None,
                        "trigger_detected",
                        trigger.model_dump(mode="json"),
                    )
                )
            log_event(
                logger,
                logging.INFO,
                "turn_triggers_evaluated",
                session_id=session_id,
                turn_id=turn_id,
                clean_text=clean_text,
                recent_texts=recent_texts,
                silence_s=silence_s,
                silence_threshold=silence_threshold,
                loop_threshold=loop_threshold,
                triggers=[trigger.model_dump(mode="json") for trigger in triggers],
            )

            scaffold_started = perf_counter()
            trigger_types = {trigger.type for trigger in triggers}
            action_type, scaffold_level = self.policy.choose_action(trigger_types)
            scaffold = self.scaffold.generate(scaffold_level, {"text": clean_text}) if scaffold_level else None
            self._record_turn_stage("scaffold", scaffold_started, session_id=session_id, turn_id=turn_id)
            if scaffold and scaffold.fired:
                events.append(
                    self._event(
                        session_id,
                        None,
                        "scaffold_fired",
                        scaffold.model_dump(mode="json"),
                    )
                )
            log_event(
                logger,
                logging.INFO,
                "turn_policy_decided",
                session_id=session_id,
                turn_id=turn_id,
                trigger_types=sorted(trigger_type.value for trigger_type in trigger_types),
                chosen_action_type=action_type.value,
                scaffold_level=scaffold_level.value if scaffold_level else None,
                scaffold=scaffold.model_dump(mode="json") if scaffold else None,
            )

            evaluation_started = perf_counter()
            eval_result = self.scoring.score(
                clean_text,
                question=current_question.text if current_question and current_question.text else "",
                scaffold_level=scaffold_level,
            )
            self._record_turn_stage("evaluation", evaluation_started, session_id=session_id, turn_id=turn_id)
            theta = self._update_theta(session.theta, eval_result.scores)
            log_event(
                logger,
                logging.INFO,
                "turn_evaluation_ready",
                session_id=session_id,
                turn_id=turn_id,
                evaluation=eval_result.model_dump(mode="json"),
                theta_previous=session.theta.model_dump(mode="json") if session.theta else None,
                theta_updated=theta.model_dump(mode="json"),
            )

            next_cursor: QuestionCursor | None
            decision_source = "selector"
            decision_reasons: dict[str, object] = {}
            if scaffold and scaffold.fired and scaffold.prompt:
                next_action = NextAction(
                    type=action_type,
                    text=scaffold.prompt,
                    level=scaffold_level,
                    payload=None,
                )
                next_cursor = self.selector.scaffold_cursor(
                    current_cursor,
                    prompt=scaffold.prompt,
                    level=scaffold.level.value if scaffold.level else "L1",
                    turn_index=turn_index + 1,
                )
                decision_source = "scaffold_prompt"
                decision_reasons = {
                    "action_type": action_type.value,
                    "scaffold_level": scaffold_level.value if scaffold_level else None,
                    "scaffold_rationale": scaffold.rationale,
                }
            elif action_type == NextActionType.CALM:
                calm_prompt = "慢一点也没关系。先说你准备从哪一步开始。"
                next_action = NextAction(type=action_type, text=calm_prompt, level=None, payload=None)
                next_cursor = self.selector.scaffold_cursor(
                    current_cursor,
                    prompt=calm_prompt,
                    level="CALM",
                    turn_index=turn_index + 1,
                )
                decision_source = "calm_action"
                decision_reasons = {
                    "action_type": action_type.value,
                    "trigger_types": sorted(trigger_type.value for trigger_type in trigger_types),
                    "calm_prompt": calm_prompt,
                }
            else:
                selection = self.selector.select_next(
                    session.question_set_id,
                    current_cursor,
                    eval_result,
                    theta,
                )
                if selection.exhausted:
                    next_action = NextAction(
                        type=NextActionType.END,
                        text="本轮面试到此结束，感谢你的回答。",
                        level=None,
                        payload=None,
                    )
                    next_cursor = None
                else:
                    next_action = NextAction(
                        type=selection.action_type,
                        text=selection.question.text if selection.question else None,
                        level=None,
                        payload=None,
                    )
                    next_cursor = selection.cursor
                decision_reasons = {
                    "action_type": selection.action_type.value,
                    "selection_exhausted": selection.exhausted,
                    "selection_prompt_kind": selection.cursor.prompt_kind if selection.cursor else None,
                    "selection_prompt_id": selection.cursor.prompt_id if selection.cursor else None,
                    "selection_node_id": selection.cursor.node_id if selection.cursor else None,
                    "selection_question_text": selection.question.text if selection.question else None,
                    "evaluation_scores": eval_result.scores.model_dump(mode="json"),
                    "evaluation_confidence": eval_result.final_confidence,
                    "theta_updated": theta.model_dump(mode="json"),
                }
            after = self.state_machine.next_state(before, next_action.type)
            log_event(
                logger,
                logging.INFO,
                "next_action_decision_logged",
                session_id=session_id,
                turn_id=turn_id,
                decision_source=decision_source,
                decision_reasons=decision_reasons,
                next_action=next_action.model_dump(mode="json"),
                next_cursor=next_cursor.model_dump(mode="json") if next_cursor else None,
                state_before=before.value,
                state_after=after.value,
            )

            turn = self._build_turn(
                turn_id=turn_id,
                turn_index=turn_index,
                req=req,
                question=current_question,
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
            self.store.update_session(
                db,
                session_id,
                state=after.value,
                last_next_action=next_action,
                current_question_cursor=next_cursor.model_dump(mode="json") if next_cursor else None,
                theta=theta.model_dump(mode="json"),
                ended_at=datetime.now(timezone.utc) if next_action.type == NextActionType.END else None,
            )
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
            self._record_turn_total(
                turn_started,
                session_id=session_id,
                turn_id=turn.turn_id,
                state_before=before.value,
                state_after=after.value,
                next_action=next_action.type.value,
            )
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
        with self.store.transaction() as db:
            session = self.store.get_session_for_update(db, session_id)
            if session is None:
                raise KeyError("session not found")

            turns = self.store.list_turns_tx(db, session_id)
            session_score = self.session_scoring.score_session(turns)
            latest = session_score.scores
            timeline = [
                ReportPoint(
                    turn_index=t.turn_index,
                    scores=t.evaluation.scores if t.evaluation else latest,
                )
                for t in turns
            ]
            report_notes = [f"ended:{reason}", *session_score.notes]
            report = Report(overall=latest, timeline=timeline, notes=report_notes)
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
            log_event(
                logger,
                logging.INFO,
                "session_ended",
                session_id=session_id,
                reason=reason,
                session_score_source=session_score.source,
                session_score_confidence=session_score.confidence,
                session_score=latest.model_dump(mode="json"),
            )
            return report

    def get_report(self, session_id: str) -> Report | None:
        return self.store.get_report(session_id)

    def get_opening_prompt(self, question_set_id: str) -> str | None:
        prompt = self.selector.next_prompt(question_set_id, 0)
        return prompt or None

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
            if not self.store.turn_belongs_to_session(db, session_id, body.turn_id):
                raise ValueError("turn_id not found in session")
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
            log_event(
                logger,
                logging.INFO,
                "annotation_created",
                session_id=session_id,
                turn_id=body.turn_id,
            )

    def _build_turn(
        self,
        turn_id: str,
        turn_index: int,
        req: TurnCreateRequest,
        question: QuestionRef | None,
        state_before: SessionState,
        state_after: SessionState,
        asr: AsrResult | None,
        preprocess: PreprocessResult,
        triggers,
        evaluation,
        next_action,
        scaffold,
    ) -> Turn:
        return Turn(
            turn_id=turn_id,
            turn_index=turn_index,
            question=question,
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

    def _question_from_cursor(self, cursor: QuestionCursor | None) -> QuestionRef | None:
        if cursor is None or not cursor.prompt_text:
            return None
        return QuestionRef(qid=cursor.prompt_id, text=cursor.prompt_text)

    def _update_theta(self, previous: DimScores | None, current: DimScores) -> DimScores:
        if previous is None:
            return current
        alpha = 0.7
        return DimScores(
            plan=round(alpha * previous.plan + (1 - alpha) * current.plan, 2),
            monitor=round(alpha * previous.monitor + (1 - alpha) * current.monitor, 2),
            evaluate=round(alpha * previous.evaluate + (1 - alpha) * current.evaluate, 2),
            adapt=round(alpha * previous.adapt + (1 - alpha) * current.adapt, 2),
        )

    def _record_turn_stage(self, stage: str, started_at: float, *, session_id: str, turn_id: str) -> None:
        duration_seconds = perf_counter() - started_at
        observe_turn_stage(stage, duration_seconds)
        log_event(
            logger,
            logging.INFO,
            "turn_stage_completed",
            session_id=session_id,
            turn_id=turn_id,
            stage=stage,
            latency_ms=round(duration_seconds * 1000, 3),
        )

    def _record_turn_total(
        self,
        started_at: float,
        *,
        session_id: str,
        turn_id: str,
        state_before: str,
        state_after: str,
        next_action: str,
    ) -> None:
        duration_seconds = perf_counter() - started_at
        observe_turn_total(duration_seconds)
        log_event(
            logger,
            logging.INFO,
            "turn_completed",
            session_id=session_id,
            turn_id=turn_id,
            state_before=state_before,
            state_after=state_after,
            next_action=next_action,
            latency_ms=round(duration_seconds * 1000, 3),
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

    def _extract_silence_seconds(self, asr_result: AsrResult | None) -> float:
        if asr_result is None or not asr_result.silence_segments:
            return 0.0
        max_segment_ms = max(
            (segment.end_ms - segment.start_ms for segment in asr_result.silence_segments),
            default=0,
        )
        if max_segment_ms <= 0:
            return 0.0
        return max_segment_ms / 1000.0

    def _ensure_session_refs_exist(self, question_set_id: str, rubric_id: str) -> None:
        if not self._json_resource_exists(self.question_set_dir, question_set_id):
            raise ValueError(f"question_set not found: {question_set_id}")
        if not self._json_resource_exists(self.rubric_dir, rubric_id):
            raise ValueError(f"rubric not found: {rubric_id}")

    def _json_resource_exists(self, directory: Path, resource_id: str) -> bool:
        if not resource_id.strip():
            return False
        path = directory / f"{resource_id}.json"
        if not path.exists() or not path.is_file():
            return False
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False
        return isinstance(payload, dict)

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
            try:
                path = self.file_store.path_for(req.input.audio_id)
            except ValueError as exc:
                raise ValueError("invalid audio_id") from exc
            if not path.exists() or not path.is_file():
                raise ValueError("audio_id not found")
            return path.read_bytes(), path.name

        if not req.input.audio_url:
            raise ValueError("audio_ref requires audio_url or audio_id")

        url = req.input.audio_url
        if url.startswith("data:"):
            return self._decode_data_url(url)

        if url.startswith("http://") or url.startswith("https://"):
            return self._download_remote_audio(url)

        raise ValueError("unsupported audio_url scheme")

    def _download_remote_audio(self, url: str) -> tuple[bytes, str]:
        if not settings.allow_remote_audio_fetch:
            raise ValueError("remote audio_url fetching is disabled")

        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("unsupported remote audio_url scheme")
        if not parsed.hostname:
            raise ValueError("invalid audio_url host")

        hostname = parsed.hostname.lower()
        if settings.remote_audio_allowed_hosts and hostname not in settings.remote_audio_allowed_hosts:
            raise ValueError("audio_url host is not allowed")
        self._assert_public_host(hostname)

        max_bytes = settings.remote_audio_max_bytes
        data = bytearray()

        import httpx

        with httpx.Client(timeout=20.0, follow_redirects=False) as client:
            with client.stream("GET", url) as resp:
                resp.raise_for_status()
                for chunk in resp.iter_bytes(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    data.extend(chunk)
                    if len(data) > max_bytes:
                        raise ValueError("audio payload too large")

        filename = parsed.path.rsplit("/", 1)[-1] or "audio.bin"
        return bytes(data), filename

    def _assert_public_host(self, hostname: str) -> None:
        try:
            address_infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
        except socket.gaierror as exc:
            raise ValueError("audio_url host cannot be resolved") from exc

        for info in address_infos:
            raw_ip = info[4][0]
            ip = ipaddress.ip_address(raw_ip)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or ip.is_unspecified
            ):
                raise ValueError("audio_url host must resolve to public IP")

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

    def _recover_turn_conflict(
        self,
        session_id: str,
        idempotency_key: str | None,
        exc: IntegrityError,
    ) -> tuple[Turn, NextAction] | None:
        if idempotency_key and self._is_idempotency_conflict(exc):
            existing_turn = self.store.find_turn_by_idempotency(session_id, idempotency_key)
            if existing_turn is not None:
                return existing_turn, self._resolve_existing_next_action(session_id, existing_turn)
        return None

    def _resolve_existing_next_action(self, session_id: str, turn: Turn) -> NextAction:
        next_action = turn.next_action or self.store.get_last_next_action(session_id)
        if next_action is None:
            return NextAction(type=NextActionType.WAIT, text="Please continue.")
        return next_action

    def _is_idempotency_conflict(self, exc: IntegrityError) -> bool:
        message = str(exc.orig).lower()
        return "uq_turn_session_idempotency" in message or "turns.session_id, turns.idempotency_key" in message

    def _is_turn_index_conflict(self, exc: IntegrityError) -> bool:
        message = str(exc.orig).lower()
        return "uq_turn_session_index" in message or "turns.session_id, turns.turn_index" in message

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

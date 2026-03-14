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
from libs.question_sets import question_set_exists
from libs.observability import log_event, observe_turn_stage, observe_turn_total
from libs.schemas.api import CursorEnvelope, HumanAnnotationCreateRequest, SessionCreateRequest, TurnCreateRequest
from libs.schemas.base import (
    AsrResult,
    NextAction,
    NextActionType,
    PreprocessResult,
    QuestionCursor,
    QuestionRef,
    Report,
    ReportDialogueMessage,
    ReportLLMScoring,
    ReportPoint,
    ReportTurnEvaluation,
    ScaffoldResult,
    Session,
    SessionReviewStatus,
    SessionState,
    Turn,
    TurnInputType,
)
from libs.storage.files import FileStore
from libs.storage.postgres import SqlStore
from sqlalchemy.exc import IntegrityError
from services.asr import ASRService
from services.dialogue.generator import DialogueGenerator
from services.evaluation.session_scorer import SessionScorer
from services.nlp.preprocess import Preprocessor
from services.orchestrator.next_action_decider import LLMNextActionDecider
from services.orchestrator.selector import QuestionSelector
from services.orchestrator.state_machine import SessionStateMachine
from services.safety.classifier import SafetyClassifier
from services.safety.prompt_injection_detector import PromptInjectionDetectionError, PromptInjectionDetector
from services.scaffold.generator import ScaffoldGenerator
from services.trigger.detector import TriggerDetector

logger = logging.getLogger(__name__)

_LAST_QUESTION_NOTICE_TEXT = "这场面试时间已经过长，这次将是你的最后一次提问"
_LAST_QUESTION_NOTICE_MARKER = "__last_question_notice_issued__"
_MAX_TURNS_PER_QUESTION = 12
_QUESTION_TURN_LIMIT_END_TEXT = "这道题先到这里，感谢你的作答。"
_PROMPT_INJECTION_WARNING_TEXT = "你进行了一次提示词注入，请不要再这样做，否则会直接停止面试"
_PROMPT_INJECTION_END_TEXT = "你再次进行了提示词注入，面试已终止，本次面试将被标记为 Invalid"
_PROMPT_INJECTION_LIMIT = 2
_PROMPT_INJECTION_REDACTED_TEXT = "[prompt injection removed]"


class CursorError(ValueError):
    pass


class OrchestratorService:
    def __init__(self) -> None:
        self.state_machine = SessionStateMachine()
        self.next_action_decider = LLMNextActionDecider()
        self.selector = QuestionSelector()
        self.preprocessor = Preprocessor()
        self.safety = SafetyClassifier()
        self.prompt_injection_detector = PromptInjectionDetector()
        self.trigger_detector = TriggerDetector()
        self.scaffold = ScaffoldGenerator()
        self.dialogue = DialogueGenerator()
        self.session_scoring = SessionScorer()
        self.asr_service = ASRService()
        self.file_store = FileStore()
        self.store = SqlStore(settings.database_url)
        self.question_set_dir = Path(__file__).resolve().parents[2] / "data" / "question_sets"
        self.rubric_dir = Path(__file__).resolve().parents[2] / "data" / "rubrics"
        self.scaffold_policy_ids = {item.strip().lower() for item in settings.scaffold_policy_ids if item.strip()}

    def create_session(self, req: SessionCreateRequest) -> tuple[Session, NextAction]:
        self._ensure_session_refs_exist(
            req.question_set_id,
            req.scoring_policy_id,
            req.scaffold_policy_id,
        )
        opening = self.selector.random_opening_selection(req.question_set_id)
        opening_seed_text = opening.question.text if opening.question else None
        opening_text = self._build_opening_prompt(opening_seed_text)
        opening_cursor = (
            opening.cursor.model_copy(update={"prompt_text": opening_text}) if opening.cursor else None
        )
        session = Session(
            session_id=f"sess_{uuid4().hex[:12]}",
            candidate=req.candidate,
            mode=req.mode,
            state=SessionState.S_INIT,
            question_set_id=req.question_set_id,
            scoring_policy_id=req.scoring_policy_id,
            scaffold_policy_id=req.scaffold_policy_id,
            thresholds=req.thresholds,
            current_question_cursor=opening_cursor,
            created_at=datetime.now(timezone.utc),
        )
        next_action = NextAction(
            type=opening.action_type,
            text=opening_text,
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

            prompt_injection_started = perf_counter()
            prompt_injection = self.prompt_injection_detector.detect(raw_text)
            self._record_turn_stage(
                "prompt_injection",
                prompt_injection_started,
                session_id=session_id,
                turn_id=turn_id,
            )
            log_event(
                logger,
                logging.INFO,
                "turn_prompt_injection_evaluated",
                session_id=session_id,
                turn_id=turn_id,
                raw_text=raw_text,
                is_prompt_injection=prompt_injection.is_prompt_injection,
                prompt_injection_category=prompt_injection.category,
                prompt_injection_confidence=prompt_injection.confidence,
                prompt_injection_reason=prompt_injection.reason,
            )
            if prompt_injection.is_prompt_injection:
                return self._handle_prompt_injection_turn(
                    db,
                    session=session,
                    req=req,
                    session_id=session_id,
                    turn_id=turn_id,
                    turn_index=turn_index,
                    before=before,
                    current_question=current_question,
                    current_cursor=current_cursor,
                    asr_result=asr_result,
                    raw_text=raw_text,
                    events=events,
                    idempotency_key=idempotency_key,
                    turn_started=turn_started,
                    prompt_injection=prompt_injection,
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
                    theta=None,
                    ended_at=datetime.now(timezone.utc),
                )
                _, session_score = self._generate_report_for_session(
                    db,
                    session_id,
                    reason="safety_block",
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
                        self._event(
                            session_id,
                            turn.turn_id,
                            "report_generated",
                            {
                                "reason": "safety_block",
                                "session_score_source": session_score.source,
                                "session_score_confidence": session_score.confidence,
                            },
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
                preprocess = preprocess.model_copy(update={"clean_text": clean_text})
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
                question_text=current_question.text if current_question else None,
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

            trigger_types = {trigger.type for trigger in triggers}

            policy_started = perf_counter()
            conversation_history = self._build_full_conversation_history(
                db,
                session_id,
                current_question=current_question,
                candidate_answer=clean_text,
                turn_index=turn_index,
            )
            elapsed_minutes = self._elapsed_minutes(session.created_at)
            last_question_notice_issued = self._last_question_notice_issued(current_cursor)
            next_cursor: QuestionCursor | None
            decision_source = "llm_policy"
            decision_reasons: dict[str, object]
            scaffold: ScaffoldResult | None = None
            llm_decision = self.next_action_decider.decide(
                conversation_history,
                elapsed_minutes=elapsed_minutes,
                last_question_notice_issued=last_question_notice_issued,
            )
            next_action = NextAction(
                type=llm_decision.action_type,
                text=llm_decision.interviewer_reply,
                level=None,
                payload=None,
            )
            time_policy_applied: str | None = None
            question_policy_applied: str | None = None
            if self._question_turn_limit_reached(current_cursor):
                next_action = NextAction(type=NextActionType.END, text=_QUESTION_TURN_LIMIT_END_TEXT)
                question_policy_applied = "force_end_after_question_turn_limit"
            if elapsed_minutes >= 30.0 or last_question_notice_issued:
                next_action = NextAction(type=NextActionType.END, text="本场面试到此结束，感谢你的作答。")
                time_policy_applied = "force_end_after_time_limit"
            issue_last_question_notice = False
            if (
                question_policy_applied is None
                and 25.0 <= elapsed_minutes < 30.0
                and not last_question_notice_issued
            ):
                if next_action.type not in {NextActionType.ASK, NextActionType.PROBE}:
                    next_action = next_action.model_copy(update={"type": NextActionType.PROBE, "level": None})
                    time_policy_applied = "last_question_coerced_to_probe"
                next_action = next_action.model_copy(update={"text": self._with_last_question_notice(next_action.text)})
                issue_last_question_notice = True
                if time_policy_applied is None:
                    time_policy_applied = "issue_last_question_notice"
            if next_action.type == NextActionType.SCAFFOLD:
                scaffold = ScaffoldResult(
                    fired=True,
                    level=None,
                    prompt=next_action.text,
                    rationale="llm_selected_scaffold",
                )
            next_cursor = None
            if next_action.type != NextActionType.END:
                next_cursor = self._cursor_for_next_action(
                    current_cursor,
                    action_type=next_action.type,
                    prompt=next_action.text or "",
                    turn_index=turn_index + 1,
                    issue_last_question_notice=issue_last_question_notice,
                )
            decision_reasons = {
                "action_type": llm_decision.action_type.value,
                "llm_reasons": list(llm_decision.reasons),
                "history_message_count": len(conversation_history),
                "trigger_types": sorted(trigger_type.value for trigger_type in trigger_types),
                "elapsed_minutes": round(elapsed_minutes, 2),
                "last_question_notice_issued": last_question_notice_issued,
                "question_policy_applied": question_policy_applied,
                "time_policy_applied": time_policy_applied,
            }

            self._record_turn_stage("policy_llm", policy_started, session_id=session_id, turn_id=turn_id)
            if next_action.type == NextActionType.SCAFFOLD:
                if scaffold is None:
                    scaffold = ScaffoldResult(
                        fired=True,
                        level=None,
                        prompt=next_action.text,
                        rationale="llm_selected_scaffold",
                    )
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
                chosen_action_type=next_action.type.value,
                decision_source=decision_source,
                decision_reasons=decision_reasons,
            )
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
                evaluation=None,
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
                theta=None,
                ended_at=datetime.now(timezone.utc) if next_action.type == NextActionType.END else None,
            )
            report_event = None
            if next_action.type == NextActionType.END:
                _, session_score = self._generate_report_for_session(
                    db,
                    session_id,
                    reason="auto_end",
                )
                report_event = self._event(
                    session_id,
                    turn.turn_id,
                    "report_generated",
                    {
                        "reason": "auto_end",
                        "session_score_source": session_score.source,
                        "session_score_confidence": session_score.confidence,
                    },
                )
            events.extend(
                [
                    self._event(
                        session_id,
                        turn.turn_id,
                        "evaluation_completed",
                        {
                            "skipped": True,
                            "reason": "turn_scoring_disabled",
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
            if report_event is not None:
                events.append(report_event)
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
            if self.store.count_events_tx(db, session_id, "session_invalidated") > 0:
                raise RuntimeError("session invalidated")

            report, session_score = self._generate_report_for_session(
                db,
                session_id,
                reason=reason,
            )
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
                session_score=report.overall.model_dump(mode="json"),
            )
            return report

    def get_report(self, session_id: str) -> Report | None:
        return self.store.get_report(session_id)

    def get_session_review_status(self, session_id: str) -> tuple[SessionReviewStatus, int, str | None]:
        session = self.get_session(session_id)
        if session is None:
            raise KeyError("session not found")
        report = self.get_report(session_id)
        return self._derive_session_review_status(session, report=report)

    def get_opening_prompt(self, question_set_id: str, node_id: str | None = None) -> str | None:
        prompt = self.selector.question_text(question_set_id, node_id)
        if not prompt:
            prompt = self.selector.next_prompt(question_set_id, 0)
        prompt = self._build_opening_prompt(prompt)
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

    def _handle_prompt_injection_turn(
        self,
        db,
        *,
        session: Session,
        req: TurnCreateRequest,
        session_id: str,
        turn_id: str,
        turn_index: int,
        before: SessionState,
        current_question: QuestionRef | None,
        current_cursor: QuestionCursor | None,
        asr_result: AsrResult | None,
        raw_text: str,
        events: list[dict],
        idempotency_key: str | None,
        turn_started: float,
        prompt_injection,
    ) -> tuple[Turn, NextAction]:
        preprocess_started = perf_counter()
        preprocess = PreprocessResult(**self.preprocessor.run(raw_text))
        preprocess = preprocess.model_copy(update={"clean_text": _PROMPT_INJECTION_REDACTED_TEXT})
        self._record_turn_stage("preprocess", preprocess_started, session_id=session_id, turn_id=turn_id)
        events.append(
            self._event(
                session_id,
                None,
                "preprocess_completed",
                preprocess.model_dump(mode="json"),
            )
        )

        prompt_injection_count = self.store.count_events_tx(db, session_id, "prompt_injection_detected") + 1
        events.append(
            self._event(
                session_id,
                turn_id,
                "prompt_injection_detected",
                {
                    "count": prompt_injection_count,
                    "category": prompt_injection.category,
                    "confidence": prompt_injection.confidence,
                    "reason": prompt_injection.reason,
                },
            )
        )

        is_invalid = prompt_injection_count >= _PROMPT_INJECTION_LIMIT
        action_type = NextActionType.END if is_invalid else NextActionType.WAIT
        next_action = NextAction(
            type=action_type,
            text=_PROMPT_INJECTION_END_TEXT if is_invalid else _PROMPT_INJECTION_WARNING_TEXT,
            level=None,
            payload={
                "interview_status": (
                    SessionReviewStatus.INVALID.value if is_invalid else SessionReviewStatus.IN_PROGRESS.value
                ),
                "prompt_injection_count": prompt_injection_count,
                "prompt_injection_warning": not is_invalid,
            },
        )
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
            current_question_cursor=None if is_invalid else (current_cursor.model_dump(mode="json") if current_cursor else None),
            ended_at=datetime.now(timezone.utc) if is_invalid else None,
        )

        if is_invalid:
            events.append(
                self._event(
                    session_id,
                    turn_id,
                    "session_invalidated",
                    {
                        "reason": "prompt_injection_limit",
                        "prompt_injection_count": prompt_injection_count,
                    },
                )
            )
        else:
            events.append(
                self._event(
                    session_id,
                    turn_id,
                    "prompt_injection_warned",
                    {
                        "prompt_injection_count": prompt_injection_count,
                    },
                )
            )
        events.extend(
            [
                self._event(
                    session_id,
                    turn.turn_id,
                    "evaluation_completed",
                    {
                        "skipped": True,
                        "reason": "prompt_injection_detected",
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
            "prompt_injection_handled",
            session_id=session_id,
            turn_id=turn_id,
            prompt_injection_count=prompt_injection_count,
            invalidated=is_invalid,
            next_action=next_action.model_dump(mode="json"),
        )
        return turn, next_action

    def _derive_session_review_status(
        self,
        session: Session,
        *,
        report: Report | None,
    ) -> tuple[SessionReviewStatus, int, str | None]:
        events = self.store.list_events(session.session_id)
        prompt_injection_count = sum(1 for event in events if event["event_type"] == "prompt_injection_detected")
        invalid_reason = None
        for event in events:
            if event["event_type"] != "session_invalidated":
                continue
            invalid_reason = str(event.get("payload", {}).get("reason") or "invalidated")
            return SessionReviewStatus.INVALID, prompt_injection_count, invalid_reason
        if report is not None or session.state == SessionState.S_END:
            return SessionReviewStatus.COMPLETED, prompt_injection_count, None
        return SessionReviewStatus.IN_PROGRESS, prompt_injection_count, None

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

    def _generate_report_for_session(self, db, session_id: str, *, reason: str):
        turns = self.store.list_turns_tx(db, session_id)
        report, session_score = self._build_report(turns, reason=reason)
        self.store.upsert_report(db, session_id, report)
        return report, session_score

    def _build_report(self, turns: list[Turn], *, reason: str):
        session_score = self.session_scoring.score_session(turns)
        overall = session_score.scores
        timeline = [
            ReportPoint(
                turn_index=turn.turn_index,
                scores=turn.evaluation.scores if turn.evaluation else overall,
            )
            for turn in turns
        ]
        conversation = self._build_conversation(turns)
        llm_scoring = ReportLLMScoring(
            source=session_score.source,
            confidence=session_score.confidence,
            overall=overall,
            turns=self._build_turn_evaluations(turns),
        )
        report_notes = [f"ended:{reason}", *session_score.notes]
        return (
            Report(
                overall=overall,
                timeline=timeline,
                conversation=conversation,
                llm_scoring=llm_scoring,
                notes=report_notes,
            ),
            session_score,
        )

    def _build_conversation(self, turns: list[Turn]) -> list[ReportDialogueMessage]:
        messages: list[ReportDialogueMessage] = []
        for turn in turns:
            if turn.question and turn.question.text:
                messages.append(
                    ReportDialogueMessage(
                        speaker="system",
                        turn_index=turn.turn_index,
                        text=turn.question.text,
                        kind="question",
                    )
                )

            answer = self._extract_turn_answer(turn)
            if answer:
                messages.append(
                    ReportDialogueMessage(
                        speaker="candidate",
                        turn_index=turn.turn_index,
                        text=answer,
                        kind="answer",
                    )
                )

            if (
                turn.next_action
                and turn.next_action.text
                and turn.next_action.type in {NextActionType.SCAFFOLD, NextActionType.END}
            ):
                messages.append(
                    ReportDialogueMessage(
                        speaker="system",
                        turn_index=turn.turn_index,
                        text=turn.next_action.text,
                        kind=turn.next_action.type.value.lower(),
                    )
                )
        return messages

    def _build_turn_evaluations(self, turns: list[Turn]) -> list[ReportTurnEvaluation]:
        items: list[ReportTurnEvaluation] = []
        for turn in turns:
            items.append(
                ReportTurnEvaluation(
                    turn_id=turn.turn_id,
                    turn_index=turn.turn_index,
                    question=turn.question.text if turn.question else None,
                    answer=self._extract_turn_answer(turn),
                    scores=turn.evaluation.scores if turn.evaluation else None,
                    final_confidence=turn.evaluation.final_confidence if turn.evaluation else None,
                    judge_votes=turn.evaluation.judge_votes if turn.evaluation else None,
                    evidence=turn.evaluation.evidence if turn.evaluation else None,
                )
            )
        return items

    def _extract_turn_answer(self, turn: Turn) -> str:
        if turn.preprocess and turn.preprocess.clean_text:
            return turn.preprocess.clean_text
        if turn.input.text:
            return turn.input.text
        if turn.asr and turn.asr.raw_text:
            return turn.asr.raw_text
        return ""

    def _build_full_conversation_history(
        self,
        db,
        session_id: str,
        *,
        current_question: QuestionRef | None,
        candidate_answer: str,
        turn_index: int,
    ) -> list[dict[str, object]]:
        history: list[dict[str, object]] = []
        turns = self.store.list_turns_tx(db, session_id)
        for turn in turns:
            if turn.question and turn.question.text:
                history.append(
                    {
                        "role": "system",
                        "turn_index": turn.turn_index,
                        "text": turn.question.text,
                    }
                )
            answer = self._extract_turn_answer(turn)
            if answer:
                history.append(
                    {
                        "role": "candidate",
                        "turn_index": turn.turn_index,
                        "text": answer,
                    }
                )

        if current_question and current_question.text:
            history.append(
                {
                    "role": "system",
                    "turn_index": turn_index,
                    "text": current_question.text,
                }
            )
        if candidate_answer.strip():
            history.append(
                {
                    "role": "candidate",
                    "turn_index": turn_index,
                    "text": candidate_answer.strip(),
                }
            )
        return history

    def _cursor_for_next_action(
        self,
        base_cursor: QuestionCursor | None,
        *,
        action_type: NextActionType,
        prompt: str,
        turn_index: int,
        issue_last_question_notice: bool = False,
    ) -> QuestionCursor:
        asked_prompt_ids = list(base_cursor.asked_prompt_ids) if base_cursor else []
        prompt_id = f"llm:{action_type.value.lower()}:{turn_index}"
        if prompt_id not in asked_prompt_ids:
            asked_prompt_ids.append(prompt_id)
        if issue_last_question_notice and _LAST_QUESTION_NOTICE_MARKER not in asked_prompt_ids:
            asked_prompt_ids.append(_LAST_QUESTION_NOTICE_MARKER)
        prompt_kind = "question" if action_type == NextActionType.ASK else action_type.value.lower()
        return QuestionCursor(
            node_id=base_cursor.node_id if base_cursor else None,
            prompt_id=prompt_id,
            prompt_kind=prompt_kind,
            prompt_text=prompt,
            asked_prompt_ids=asked_prompt_ids,
        )

    def _elapsed_minutes(self, created_at: datetime) -> float:
        delta = datetime.now(timezone.utc) - created_at
        return max(0.0, delta.total_seconds() / 60.0)

    def _last_question_notice_issued(self, cursor: QuestionCursor | None) -> bool:
        if cursor is None:
            return False
        return _LAST_QUESTION_NOTICE_MARKER in cursor.asked_prompt_ids

    def _question_turn_limit_reached(self, cursor: QuestionCursor | None) -> bool:
        if cursor is None:
            return False
        prompt_count = sum(1 for prompt_id in cursor.asked_prompt_ids if prompt_id != _LAST_QUESTION_NOTICE_MARKER)
        return prompt_count >= _MAX_TURNS_PER_QUESTION

    def _with_last_question_notice(self, text: str | None) -> str:
        prompt = (text or "").strip()
        if not prompt:
            return f"{_LAST_QUESTION_NOTICE_TEXT}。请你总结你最关键的一步思路与验证方式。"
        if prompt.startswith(_LAST_QUESTION_NOTICE_TEXT):
            return prompt
        separator = "。" if not prompt.startswith(("，", "。", "；", "：")) else ""
        return f"{_LAST_QUESTION_NOTICE_TEXT}{separator}{prompt}"

    def _build_opening_prompt(self, seed_text: str | None) -> str:
        guidance = "不要着急作答，先说说你打算怎么做。"
        question = (seed_text or "").strip()
        if not question:
            return guidance
        return f"{question}{guidance}"

    def _question_from_cursor(self, cursor: QuestionCursor | None) -> QuestionRef | None:
        if cursor is None or not cursor.prompt_text:
            return None
        return QuestionRef(qid=cursor.prompt_id, text=cursor.prompt_text)

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

    def _ensure_session_refs_exist(
        self,
        question_set_id: str,
        rubric_id: str,
        scaffold_policy_id: str,
    ) -> None:
        if not question_set_exists(self.question_set_dir, question_set_id):
            raise ValueError(f"question_set not found: {question_set_id}")
        if not self._json_resource_exists(self.rubric_dir, rubric_id):
            raise ValueError(f"rubric not found: {rubric_id}")
        if scaffold_policy_id.strip().lower() not in self.scaffold_policy_ids:
            raise ValueError(f"scaffold_policy not found: {scaffold_policy_id}")

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

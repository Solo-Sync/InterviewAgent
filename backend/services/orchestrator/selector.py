from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from libs.schemas.base import DimScores, EvaluationResult, NextActionType, QuestionCursor, QuestionRef


@dataclass(frozen=True)
class PromptSpec:
    prompt_id: str
    prompt: str
    kind: str
    when: str | None = None
    trigger: str | None = None


@dataclass(frozen=True)
class QuestionNode:
    qid: str
    text: str
    probes: tuple[PromptSpec, ...]
    perturbations: tuple[PromptSpec, ...]
    children: tuple[str, ...]


@dataclass(frozen=True)
class QuestionSetBundle:
    order: tuple[str, ...]
    nodes: dict[str, QuestionNode]


@dataclass(frozen=True)
class QuestionSelection:
    action_type: NextActionType
    question: QuestionRef | None
    cursor: QuestionCursor | None
    exhausted: bool = False


class QuestionSelector:
    def __init__(self) -> None:
        self._question_set_dir = Path(__file__).resolve().parents[2] / "data" / "question_sets"
        self._cache: dict[str, QuestionSetBundle] = {}

    def opening_selection(self, question_set_id: str) -> QuestionSelection:
        bundle = self._load_question_set(question_set_id)
        if not bundle.order:
            return self._fallback_selection(turn_index=0)
        first = bundle.nodes[bundle.order[0]]
        return self._selection_for_prompt(first.qid, first.qid, "question", first.text, [], NextActionType.ASK)

    def select_next(
        self,
        question_set_id: str,
        cursor: QuestionCursor | None,
        evaluation: EvaluationResult | None,
        theta: DimScores | None,
    ) -> QuestionSelection:
        bundle = self._load_question_set(question_set_id)
        if not bundle.order:
            turn_index = len(cursor.asked_prompt_ids) if cursor else 0
            return self._fallback_selection(turn_index=turn_index)

        current = cursor or self.opening_selection(question_set_id).cursor
        if current is None:
            return QuestionSelection(action_type=NextActionType.END, question=None, cursor=None, exhausted=True)

        current_node = bundle.nodes.get(current.node_id or "") or bundle.nodes[bundle.order[0]]
        asked_prompt_ids = list(current.asked_prompt_ids)
        asked_prompt_set = set(asked_prompt_ids)
        low_dimensions, good_flow = self._quality_signals(evaluation, theta)

        for probe in current_node.probes:
            if probe.prompt_id in asked_prompt_set or not self._probe_matches(probe, low_dimensions):
                continue
            return self._selection_for_prompt(
                current_node.qid,
                probe.prompt_id,
                probe.kind,
                probe.prompt,
                asked_prompt_ids,
                NextActionType.PROBE,
            )

        if good_flow:
            for perturbation in current_node.perturbations:
                if perturbation.prompt_id in asked_prompt_set or not self._perturbation_matches(perturbation, good_flow):
                    continue
                return self._selection_for_prompt(
                    current_node.qid,
                    perturbation.prompt_id,
                    perturbation.kind,
                    perturbation.prompt,
                    asked_prompt_ids,
                    NextActionType.ASK,
                )

        for child_qid in current_node.children:
            if child_qid in asked_prompt_set:
                continue
            child = bundle.nodes.get(child_qid)
            if child is None:
                continue
            return self._selection_for_prompt(child.qid, child.qid, "question", child.text, asked_prompt_ids, NextActionType.ASK)

        next_node = self._next_node(bundle, current_node.qid, asked_prompt_set)
        if next_node is not None:
            return self._selection_for_prompt(next_node.qid, next_node.qid, "question", next_node.text, asked_prompt_ids, NextActionType.ASK)

        return QuestionSelection(action_type=NextActionType.END, question=None, cursor=None, exhausted=True)

    def scaffold_cursor(
        self,
        base_cursor: QuestionCursor | None,
        *,
        prompt: str,
        level: str,
        turn_index: int,
    ) -> QuestionCursor:
        asked_prompt_ids = list(base_cursor.asked_prompt_ids) if base_cursor else []
        node_id = base_cursor.node_id if base_cursor else None
        return QuestionCursor(
            node_id=node_id,
            prompt_id=f"scaffold:{level}:{turn_index}",
            prompt_kind="scaffold",
            prompt_text=prompt,
            asked_prompt_ids=asked_prompt_ids,
        )

    def next_prompt(self, question_set_id: str, turn_index: int) -> str:
        selection = self.opening_selection(question_set_id)
        if turn_index == 0 and selection.question and selection.question.text:
            return selection.question.text
        fallback = self._fallback_selection(turn_index)
        return selection.question.text if selection.question and selection.question.text else fallback.question.text or ""

    def _fallback_selection(self, turn_index: int) -> QuestionSelection:
        if turn_index == 0:
            prompt = "请先说说你会如何拆解这个问题。"
            return self._selection_for_prompt("fallback_q0", "fallback_q0", "question", prompt, [], NextActionType.ASK)
        prompt = "继续，请说明你如何验证当前假设。"
        return self._selection_for_prompt(
            "fallback_q0",
            f"fallback_probe_{turn_index}",
            "probe",
            prompt,
            ["fallback_q0"],
            NextActionType.PROBE,
        )

    def _selection_for_prompt(
        self,
        node_id: str,
        prompt_id: str,
        prompt_kind: str,
        prompt_text: str,
        asked_prompt_ids: list[str],
        action_type: NextActionType,
    ) -> QuestionSelection:
        updated_asked = list(asked_prompt_ids)
        if prompt_id not in updated_asked:
            updated_asked.append(prompt_id)
        question = QuestionRef(qid=prompt_id, text=prompt_text)
        cursor = QuestionCursor(
            node_id=node_id,
            prompt_id=prompt_id,
            prompt_kind=prompt_kind,
            prompt_text=prompt_text,
            asked_prompt_ids=updated_asked,
        )
        return QuestionSelection(action_type=action_type, question=question, cursor=cursor)

    def _quality_signals(
        self,
        evaluation: EvaluationResult | None,
        theta: DimScores | None,
    ) -> tuple[set[str], bool]:
        if evaluation is None:
            return set(), False
        score_map = {
            "plan": evaluation.scores.plan,
            "monitor": evaluation.scores.monitor,
            "evaluate": evaluation.scores.evaluate,
            "adapt": evaluation.scores.adapt,
        }
        low_dimensions = {dimension for dimension, value in score_map.items() if value < 1.5}
        avg_score = sum(score_map.values()) / len(score_map)
        theta_avg = None
        if theta is not None:
            theta_avg = (theta.plan + theta.monitor + theta.evaluate + theta.adapt) / 4
        good_flow = avg_score >= 1.8 and evaluation.final_confidence is not None and evaluation.final_confidence >= 0.55
        if theta_avg is not None:
            good_flow = good_flow and theta_avg >= 1.6
        return low_dimensions, good_flow

    def _probe_matches(self, probe: PromptSpec, low_dimensions: set[str]) -> bool:
        if not probe.when:
            return True
        if probe.when == "any_low":
            return bool(low_dimensions)
        if probe.when.endswith("_low"):
            return probe.when[: -len("_low")] in low_dimensions
        return True

    def _perturbation_matches(self, perturbation: PromptSpec, good_flow: bool) -> bool:
        if not perturbation.trigger:
            return True
        if perturbation.trigger == "good_flow":
            return good_flow
        return True

    def _next_node(
        self,
        bundle: QuestionSetBundle,
        current_qid: str,
        asked_prompt_ids: set[str],
    ) -> QuestionNode | None:
        if current_qid not in bundle.order:
            for qid in bundle.order:
                if qid not in asked_prompt_ids:
                    return bundle.nodes[qid]
            return None
        current_index = bundle.order.index(current_qid)
        for qid in bundle.order[current_index + 1 :]:
            if qid not in asked_prompt_ids:
                return bundle.nodes[qid]
        return None

    def _load_question_set(self, question_set_id: str) -> QuestionSetBundle:
        if question_set_id in self._cache:
            return self._cache[question_set_id]

        path = self._question_set_dir / f"{question_set_id}.json"
        if not path.exists():
            bundle = QuestionSetBundle(order=(), nodes={})
            self._cache[question_set_id] = bundle
            return bundle

        payload = json.loads(path.read_text(encoding="utf-8"))
        questions = payload.get("questions") or []
        nodes: dict[str, QuestionNode] = {}
        order: list[str] = []
        if isinstance(questions, list):
            for index, question in enumerate(questions):
                if isinstance(question, dict):
                    self._register_node(question, nodes, order, fallback_qid=f"q{index + 1}")

        bundle = QuestionSetBundle(order=tuple(order), nodes=nodes)
        self._cache[question_set_id] = bundle
        return bundle

    def _register_node(
        self,
        payload: dict,
        nodes: dict[str, QuestionNode],
        order: list[str],
        *,
        fallback_qid: str,
    ) -> str | None:
        qid = str(payload.get("qid") or payload.get("question_id") or fallback_qid).strip()
        text = str(payload.get("text") or "").strip()
        if not qid or not text:
            return None

        if qid not in order:
            order.append(qid)

        child_payloads = payload.get("children") or []
        child_ids: list[str] = []
        if isinstance(child_payloads, list):
            for child_index, child in enumerate(child_payloads):
                if not isinstance(child, dict):
                    continue
                child_qid = self._register_node(
                    child,
                    nodes,
                    order,
                    fallback_qid=f"{qid}_child_{child_index + 1}",
                )
                if child_qid:
                    child_ids.append(child_qid)

        node = QuestionNode(
            qid=qid,
            text=text,
            probes=self._parse_prompts(qid, payload.get("probes"), kind="probe"),
            perturbations=self._parse_prompts(qid, payload.get("perturbations"), kind="perturbation"),
            children=tuple(child_ids),
        )
        nodes[qid] = node
        return qid

    def _parse_prompts(self, qid: str, raw_prompts, *, kind: str) -> tuple[PromptSpec, ...]:
        if not isinstance(raw_prompts, list):
            return ()

        items: list[PromptSpec] = []
        for index, prompt in enumerate(raw_prompts):
            if isinstance(prompt, dict):
                prompt_id = str(prompt.get("id") or f"{qid}:{kind}:{index + 1}").strip()
                prompt_text = str(prompt.get("prompt") or prompt.get("text") or "").strip()
                when = str(prompt.get("when") or "").strip() or None
                trigger = str(prompt.get("trigger") or "").strip() or None
            else:
                prompt_id = f"{qid}:{kind}:{index + 1}"
                prompt_text = str(prompt).strip()
                when = None
                trigger = None
            if not prompt_text:
                continue
            items.append(PromptSpec(prompt_id=prompt_id, prompt=prompt_text, kind=kind, when=when, trigger=trigger))
        return tuple(items)

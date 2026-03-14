from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

_COMPOSITE_QUESTION_SET_DEFS: dict[str, dict[str, Any]] = {
    "qs_fermi_v1": {
        "title": "Fermi Estimation v1",
        "description": "Virtual bundle composed from per-question Fermi JSON files.",
        "source_ids": (
            "qs_fermi_complex_airport_luggage_v1",
            "qs_fermi_complex_food_delivery_v1",
            "qs_fermi_complex_library_seats_v1",
            "qs_fermi_complex_mall_restroom_v1",
            "qs_fermi_complex_short_video_v1",
            "qs_fermi_complex_ev_charging_v1",
        ),
    }
}


def load_question_set_payload(directory: Path, question_set_id: str) -> dict[str, Any] | None:
    payload = _load_payload_from_file(directory / f"{question_set_id}.json")
    if payload is not None:
        return payload

    composite = _COMPOSITE_QUESTION_SET_DEFS.get(question_set_id)
    if composite is None:
        return None

    questions: list[dict[str, Any]] = []
    next_qid = 1
    for source_id in composite["source_ids"]:
        source_payload = _load_payload_from_file(directory / f"{source_id}.json")
        if source_payload is None:
            return None
        raw_questions = source_payload.get("questions")
        if not isinstance(raw_questions, list):
            return None
        for question in raw_questions:
            if not isinstance(question, dict):
                continue
            item = deepcopy(question)
            synthetic_qid = str(next_qid)
            item["qid"] = synthetic_qid
            item["question_id"] = synthetic_qid
            questions.append(item)
            next_qid += 1

    return {
        "question_set_id": question_set_id,
        "title": composite["title"],
        "description": composite["description"],
        "questions": questions,
    }


def question_set_exists(directory: Path, question_set_id: str) -> bool:
    return load_question_set_payload(directory, question_set_id) is not None


def _load_payload_from_file(path: Path) -> dict[str, Any] | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None

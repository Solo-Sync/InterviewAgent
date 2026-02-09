import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from apps.api.response import ok

router = APIRouter(tags=["admin"])

BASE = Path(__file__).resolve().parents[3]
QUESTION_SET_DIR = BASE / "data" / "question_sets"
RUBRIC_DIR = BASE / "data" / "rubrics"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/admin/question_sets")
def list_question_sets(request: Request):
    items = []
    for path in sorted(QUESTION_SET_DIR.glob("*.json")):
        payload = _load_json(path)
        items.append(
            {
                "question_set_id": payload.get("question_set_id"),
                "title": payload.get("title") or payload.get("name") or payload.get("question_set_id"),
                "description": payload.get("description"),
            }
        )
    return ok(request, {"items": items})


@router.get("/admin/question_sets/{question_set_id}")
def get_question_set(request: Request, question_set_id: str):
    path = QUESTION_SET_DIR / f"{question_set_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="question_set not found")
    payload = _load_json(path)
    question_set = {
        "question_set_id": payload.get("question_set_id"),
        "title": payload.get("title") or payload.get("name") or payload.get("question_set_id"),
        "description": payload.get("description"),
        "questions": payload.get("questions", []),
    }
    return ok(request, {"question_set": question_set})


@router.get("/admin/rubrics")
def list_rubrics(request: Request):
    items = []
    for path in sorted(RUBRIC_DIR.glob("*.json")):
        payload = _load_json(path)
        items.append(
            {
                "rubric_id": payload.get("rubric_id"),
                "title": payload.get("title") or payload.get("name") or payload.get("rubric_id"),
                "description": payload.get("description"),
            }
        )
    return ok(request, {"items": items})


@router.get("/admin/rubrics/{rubric_id}")
def get_rubric(request: Request, rubric_id: str):
    path = RUBRIC_DIR / f"{rubric_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="rubric not found")
    payload = _load_json(path)
    rubric = {
        "rubric_id": payload.get("rubric_id"),
        "title": payload.get("title") or payload.get("name") or payload.get("rubric_id"),
        "description": payload.get("description"),
        "scale": payload.get("scale", {}),
    }
    return ok(request, {"rubric": rubric})

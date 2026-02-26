from fastapi import APIRouter, Request

from apps.api.core.response import ok
from libs.schemas.api import ApiResponseSafetyCheck, SafetyCheckRequest
from services.safety.classifier import SafetyClassifier

router = APIRouter(tags=["safety"])
classifier = SafetyClassifier()


@router.post("/safety/check", response_model=ApiResponseSafetyCheck)
def safety_check(request: Request, body: SafetyCheckRequest):
    return ok(request, classifier.check(body.text))

from fastapi import APIRouter, Request

from apps.api.response import ok
from libs.schemas.api import SafetyCheckRequest
from services.safety.classifier import SafetyClassifier

router = APIRouter(tags=["safety"])
classifier = SafetyClassifier()


@router.post("/safety/check")
def safety_check(request: Request, body: SafetyCheckRequest):
    return ok(request, classifier.check(body.text))

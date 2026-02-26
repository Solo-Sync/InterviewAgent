from fastapi import APIRouter, Request

from apps.api.core.response import ok
from libs.schemas.api import ApiResponsePreprocess, PreprocessRequest
from services.nlp.preprocess import Preprocessor

router = APIRouter(tags=["nlp"])
preprocessor = Preprocessor()


@router.post("/nlp/preprocess", response_model=ApiResponsePreprocess)
def preprocess(request: Request, body: PreprocessRequest):
    result = preprocessor.run(body.text)
    return ok(request, {"preprocess": result})

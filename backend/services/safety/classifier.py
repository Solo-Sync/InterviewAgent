from libs.schemas.base import SafetyAction, SafetyCategory
from services.safety.rules import BLOCK_TERMS


class SafetyClassifier:
    def check(self, text: str) -> dict:
        source = text or ""

        if any(term in source for term in BLOCK_TERMS):
            return {
                "is_safe": False,
                "category": SafetyCategory.SENSITIVE.value,
                "action": SafetyAction.BLOCK.value,
                "sanitized_text": None,
            }

        return {
            "is_safe": True,
            "category": SafetyCategory.OK.value,
            "action": SafetyAction.ALLOW.value,
            "sanitized_text": source,
        }

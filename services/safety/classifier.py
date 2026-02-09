from libs.schemas.base import SafetyAction, SafetyCategory
from services.safety.rules import BLOCK_TERMS, PROMPT_INJECTION_TERMS


class SafetyClassifier:
    def check(self, text: str) -> dict:
        lowered = text.lower()
        if any(term in text for term in BLOCK_TERMS):
            return {
                "is_safe": False,
                "category": SafetyCategory.SENSITIVE.value,
                "action": SafetyAction.BLOCK.value,
                "sanitized_text": None,
            }
        if any(term in lowered for term in PROMPT_INJECTION_TERMS):
            sanitized = lowered.replace("ignore previous", "").strip()
            return {
                "is_safe": True,
                "category": SafetyCategory.PROMPT_INJECTION.value,
                "action": SafetyAction.SANITIZE.value,
                "sanitized_text": sanitized,
            }
        return {
            "is_safe": True,
            "category": SafetyCategory.OK.value,
            "action": SafetyAction.ALLOW.value,
            "sanitized_text": text,
        }

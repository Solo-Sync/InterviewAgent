import re

from libs.schemas.base import SafetyAction, SafetyCategory
from services.safety.rules import BLOCK_TERMS, PROMPT_INJECTION_TERMS


class SafetyClassifier:
    def check(self, text: str) -> dict:
        source = text or ""
        lowered = source.lower()

        if any(term in source for term in BLOCK_TERMS):
            return {
                "is_safe": False,
                "category": SafetyCategory.SENSITIVE.value,
                "action": SafetyAction.BLOCK.value,
                "sanitized_text": None,
            }

        if any(term.lower() in lowered for term in PROMPT_INJECTION_TERMS):
            sanitized = self._sanitize_prompt_injection(source)
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
            "sanitized_text": source,
        }

    def _sanitize_prompt_injection(self, text: str) -> str:
        sanitized = text
        for term in PROMPT_INJECTION_TERMS:
            pattern = re.compile(re.escape(term), flags=re.IGNORECASE)
            sanitized = pattern.sub("", sanitized)
        sanitized = re.sub(r"\s+", " ", sanitized).strip()
        return sanitized or text

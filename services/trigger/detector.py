from libs.schemas.base import Trigger, TriggerType
from services.trigger.features import extract_features


class TriggerDetector:
    def detect(self, clean_text: str, silence_s: int = 0) -> list[Trigger]:
        features = extract_features(clean_text)
        triggers: list[Trigger] = []

        if silence_s >= 15:
            triggers.append(Trigger(type=TriggerType.SILENCE, score=0.9, detail="long silence"))
        if features["help_hits"] > 0:
            triggers.append(Trigger(type=TriggerType.HELP_KEYWORD, score=0.8, detail="asks for help"))
        if features["token_count"] <= 2:
            triggers.append(Trigger(type=TriggerType.OFFTRACK, score=0.6, detail="too short"))

        return triggers

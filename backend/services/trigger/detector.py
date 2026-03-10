from libs.schemas.base import Trigger, TriggerType
from services.trigger.features import extract_features, text_similarity
from services.trigger.offtrack_classifier import OfftrackClassifier


class TriggerDetector:
    def __init__(self) -> None:
        self.offtrack_classifier = OfftrackClassifier()

    def detect(
        self,
        clean_text: str,
        *,
        question_text: str | None = None,
        recent_texts: list[str] | None = None,
        silence_s: float = 0.0,
        silence_threshold_s: float = 15.0,
        loop_threshold: float = 0.8,
    ) -> list[Trigger]:
        features = extract_features(clean_text)
        triggers: list[Trigger] = []

        if silence_s >= silence_threshold_s:
            triggers.append(
                Trigger(
                    type=TriggerType.SILENCE,
                    score=0.9,
                    detail=f"silence {silence_s:.1f}s >= {silence_threshold_s:.1f}s",
                )
            )
        if features["help_hits"] > 0:
            triggers.append(Trigger(type=TriggerType.HELP_KEYWORD, score=0.8, detail="asks for help"))
        if features["stress_hits"] > 0 or features["exclamation_count"] >= 3:
            triggers.append(Trigger(type=TriggerType.STRESS_SIGNAL, score=0.85, detail="stress language detected"))
        if features["length"] <= 8 and features["token_count"] <= 1:
            triggers.append(Trigger(type=TriggerType.OFFTRACK, score=0.6, detail="too short"))
        if features["token_count"] >= 6:
            offtrack = self.offtrack_classifier.predict(clean_text, question_text=question_text)
            if offtrack.is_offtrack:
                triggers.append(
                    Trigger(
                        type=TriggerType.OFFTRACK,
                        score=offtrack.score,
                        detail=offtrack.detail,
                    )
                )
        if recent_texts:
            similarities = [
                text_similarity(clean_text, previous)
                for previous in recent_texts
                if (previous or "").strip()
            ]
            if similarities:
                best_similarity = max(similarities)
                if best_similarity >= loop_threshold:
                    triggers.append(
                        Trigger(
                            type=TriggerType.LOOP,
                            score=round(best_similarity, 2),
                            detail=f"similarity {best_similarity:.2f} >= {loop_threshold:.2f}",
                        )
                    )

        return triggers

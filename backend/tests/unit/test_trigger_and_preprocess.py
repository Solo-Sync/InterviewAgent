from services.nlp.preprocess import Preprocessor
from services.trigger.detector import TriggerDetector


def test_preprocess_handles_chinese_without_whitespace() -> None:
    preprocessor = Preprocessor()

    result = preprocessor.run("嗯我先定义范围然后验证假设")

    assert result["clean_text"]
    assert result["filler_stats"]["count"] >= 1
    assert result["hesitation_rate"] > 0


def test_trigger_detector_does_not_mark_long_chinese_as_offtrack() -> None:
    detector = TriggerDetector()

    triggers = detector.detect("我先定义范围并拆分变量，最后交叉验证数量级是否合理")

    assert all(trigger.type.value != "OFFTRACK" for trigger in triggers)


def test_trigger_detector_marks_silence_using_threshold() -> None:
    detector = TriggerDetector()

    triggers = detector.detect("继续思考中", silence_s=16.0, silence_threshold_s=15.0)

    assert any(trigger.type.value == "SILENCE" for trigger in triggers)


def test_trigger_detector_marks_stress_signal() -> None:
    detector = TriggerDetector()

    triggers = detector.detect("我现在非常紧张，有点慌，脑子一片空白。")

    assert any(trigger.type.value == "STRESS_SIGNAL" for trigger in triggers)


def test_trigger_detector_marks_loop_against_recent_texts() -> None:
    detector = TriggerDetector()

    triggers = detector.detect(
        "我会先定义范围再拆分变量，然后验证数量级。",
        recent_texts=["我会先定义范围再拆分变量，然后验证数量级。"],
        loop_threshold=0.8,
    )

    assert any(trigger.type.value == "LOOP" for trigger in triggers)

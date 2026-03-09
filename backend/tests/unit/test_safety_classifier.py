from services.safety.classifier import SafetyClassifier


def test_normal_text_is_allowed_without_sanitizing() -> None:
    classifier = SafetyClassifier()

    result = classifier.check("我先定义范围再估算")

    assert result["is_safe"] is True
    assert result["action"] == "ALLOW"
    assert result["sanitized_text"] == "我先定义范围再估算"


def test_sensitive_text_is_blocked() -> None:
    classifier = SafetyClassifier()

    result = classifier.check("我想讨论炸弹")

    assert result["is_safe"] is False
    assert result["action"] == "BLOCK"

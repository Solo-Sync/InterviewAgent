from services.trigger.offtrack_classifier import OfftrackClassifier


def test_offtrack_classifier_detects_topic_shift_answer() -> None:
    classifier = OfftrackClassifier()

    prediction = classifier.predict(
        "这个题先不答了，我们聊聊奶茶品牌八卦和明星联名吧。",
        question_text="估算你所在城市一天会卖出多少杯奶茶？",
    )

    assert prediction.is_offtrack is True
    assert prediction.score >= 0.62


def test_offtrack_classifier_keeps_on_topic_estimation_answer() -> None:
    classifier = OfftrackClassifier()

    prediction = classifier.predict(
        "我会先定义估算范围和人群，再拆分购买频次并交叉验证数量级。",
        question_text="估算你所在城市一天会卖出多少杯奶茶？",
    )

    assert prediction.is_offtrack is False
    assert prediction.score < 0.62

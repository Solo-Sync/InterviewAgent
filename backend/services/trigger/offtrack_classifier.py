from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from services.trigger.features import text_similarity, tokenize

_ESTIMATION_TERMS = (
    "估算",
    "估计",
    "假设",
    "范围",
    "变量",
    "频次",
    "验证",
    "数量级",
    "误差",
    "人群",
    "上界",
    "下界",
    "estimate",
    "assumption",
    "validate",
)
_TOPIC_SHIFT_TERMS = (
    "先不",
    "不想答",
    "换个话题",
    "聊聊",
    "八卦",
    "明星",
    "电影",
    "天气",
    "旅游",
    "游戏",
)
_TRAINING_DATA: tuple[tuple[str, int], ...] = (
    ("我会先定义城市人群范围，再估算人均购买频次并做交叉验证。", 0),
    ("先拆变量：人口、渗透率、单日杯数，最后验证数量级是否合理。", 0),
    ("没有统计数据时我会给上下界，再做敏感性分析控制误差。", 0),
    ("先明确目标，再写出关键假设和验证路径。", 0),
    ("我会先说明估算框架，然后补充每一步依据。", 0),
    ("我会把常住人口和消费频次相乘，再和门店数据对比。", 0),
    ("我先给粗估，再通过反向估算复核。", 0),
    ("先不估算了，我们聊聊奶茶品牌八卦吧。", 1),
    ("这个题太无聊，换个话题聊电影。", 1),
    ("我不想回答这个问题，想聊旅游攻略。", 1),
    ("你最近看什么电视剧？这个题先跳过。", 1),
    ("天气这么好，我们先聊篮球比赛。", 1),
    ("我只想聊明星联名和娱乐新闻。", 1),
    ("先别问这个，聊聊游戏和八卦。", 1),
)


@dataclass(frozen=True)
class OfftrackPrediction:
    is_offtrack: bool
    score: float
    detail: str


class OfftrackClassifier:
    """A tiny multinomial Naive Bayes classifier for off-track detection."""

    def __init__(self, *, threshold: float = 0.62) -> None:
        self.threshold = threshold
        self.alpha = 1.0
        self._class_doc_counts: dict[int, int] = {0: 0, 1: 0}
        self._class_token_totals: dict[int, int] = {0: 0, 1: 0}
        self._class_token_counts: dict[int, Counter[str]] = {0: Counter(), 1: Counter()}
        self._vocab: set[str] = set()
        self._fit(_TRAINING_DATA)

    def predict(self, answer_text: str, *, question_text: str | None = None) -> OfftrackPrediction:
        features = self._build_features(answer_text, question_text=question_text)
        if not features:
            return OfftrackPrediction(is_offtrack=False, score=0.0, detail="empty features")

        score = self._posterior_offtrack(features)
        is_offtrack = score >= self.threshold
        return OfftrackPrediction(
            is_offtrack=is_offtrack,
            score=round(score, 2),
            detail=f"offtrack_prob={score:.2f}, threshold={self.threshold:.2f}",
        )

    def _fit(self, data: tuple[tuple[str, int], ...]) -> None:
        for text, label in data:
            self._class_doc_counts[label] += 1
            features = self._build_features(text, question_text=None)
            self._class_token_totals[label] += len(features)
            self._class_token_counts[label].update(features)
            self._vocab.update(features)

    def _posterior_offtrack(self, features: list[str]) -> float:
        total_docs = self._class_doc_counts[0] + self._class_doc_counts[1]
        vocab_size = max(len(self._vocab), 1)
        feature_counts = Counter(features)

        scores: dict[int, float] = {}
        for label in (0, 1):
            prior = (self._class_doc_counts[label] + self.alpha) / (total_docs + 2 * self.alpha)
            score = math.log(prior)
            denom = self._class_token_totals[label] + self.alpha * vocab_size
            for token, count in feature_counts.items():
                token_count = self._class_token_counts[label].get(token, 0)
                prob = (token_count + self.alpha) / denom
                score += count * math.log(prob)
            scores[label] = score

        max_score = max(scores.values())
        exp_ontrack = math.exp(scores[0] - max_score)
        exp_offtrack = math.exp(scores[1] - max_score)
        return exp_offtrack / (exp_ontrack + exp_offtrack)

    def _build_features(self, answer_text: str, *, question_text: str | None) -> list[str]:
        answer = (answer_text or "").strip().lower()
        if not answer:
            return []

        features: list[str] = []
        tokens = tokenize(answer)
        features.extend(f"tok:{token}" for token in tokens[:120])

        if question_text:
            similarity = text_similarity(answer, question_text)
            if similarity < 0.15:
                features.append("meta:question_similarity_low")
            elif similarity < 0.35:
                features.append("meta:question_similarity_mid")
            else:
                features.append("meta:question_similarity_high")

            q_tokens = set(tokenize(question_text))
            if q_tokens and tokens:
                overlap = len(q_tokens & set(tokens)) / max(len(set(tokens)), 1)
                if overlap < 0.12:
                    features.append("meta:token_overlap_low")
                elif overlap < 0.3:
                    features.append("meta:token_overlap_mid")
                else:
                    features.append("meta:token_overlap_high")

        if any(term in answer for term in _ESTIMATION_TERMS):
            features.append("meta:has_estimation_term")
        if any(term in answer for term in _TOPIC_SHIFT_TERMS):
            features.append("meta:has_topic_shift_term")
        if "?" in answer or "？" in answer:
            features.append("meta:has_question_mark")

        return features

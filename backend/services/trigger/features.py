import re
from difflib import SequenceMatcher

TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")
HELP_KEYWORDS = ("不会", "不知道", "帮帮我", "help", "stuck", "i don't know")
STRESS_KEYWORDS = (
    "紧张",
    "慌",
    "慌张",
    "压力太大",
    "害怕",
    "panic",
    "anxious",
    "nervous",
    "overwhelmed",
    "blanking",
    "脑子一片空白",
)


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall((text or "").strip().lower())


def text_similarity(left: str, right: str) -> float:
    a = (left or "").strip().lower()
    b = (right or "").strip().lower()
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0

    a_tokens = set(tokenize(a))
    b_tokens = set(tokenize(b))
    token_score = len(a_tokens & b_tokens) / max(len(a_tokens | b_tokens), 1)
    sequence_score = SequenceMatcher(a=a, b=b).ratio()
    return max(token_score, sequence_score)


def extract_features(text: str) -> dict:
    source = (text or "").strip()
    lowered = source.lower()
    tokens = tokenize(source)
    return {
        "length": len(source),
        "token_count": len(tokens),
        "help_hits": sum(1 for keyword in HELP_KEYWORDS if keyword in lowered or keyword in source),
        "stress_hits": sum(1 for keyword in STRESS_KEYWORDS if keyword in lowered or keyword in source),
        "exclamation_count": source.count("!") + source.count("！"),
    }

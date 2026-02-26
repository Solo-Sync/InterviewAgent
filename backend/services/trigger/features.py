def extract_features(text: str) -> dict:
    tokens = text.split()
    return {
        "length": len(text),
        "token_count": len(tokens),
        "help_hits": int(any(k in text for k in ["不会", "help", "不知道"])),
    }

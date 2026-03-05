import re

TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+")


class Preprocessor:
    FILLERS = ("嗯", "啊", "呃", "就是", "然后")

    def run(self, text: str) -> dict:
        source = (text or "").strip()
        tokens = TOKEN_RE.findall(source)

        filler_count = sum(source.count(filler) for filler in self.FILLERS)
        clean_text = source
        for filler in self.FILLERS:
            clean_text = clean_text.replace(filler, " ")
        clean_text = re.sub(r"\s+", " ", clean_text).strip()

        hesitation_rate = filler_count / max(len(tokens), 1)
        return {
            "clean_text": clean_text or source,
            "filler_stats": {"count": filler_count},
            "hesitation_rate": hesitation_rate,
        }

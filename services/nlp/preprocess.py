class Preprocessor:
    FILLERS = {"嗯", "啊", "呃", "就是", "然后"}

    def run(self, text: str) -> dict:
        tokens = text.split()
        filler_count = sum(1 for t in tokens if t in self.FILLERS)
        clean = " ".join(t for t in tokens if t not in self.FILLERS).strip()
        hesitation_rate = filler_count / max(len(tokens), 1)
        return {
            "clean_text": clean or text,
            "filler_stats": {"count": filler_count},
            "hesitation_rate": hesitation_rate,
        }

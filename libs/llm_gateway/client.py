class LLMGateway:
    async def complete(self, model: str, prompt: str, timeout_s: float = 3.0) -> dict:
        return {
            "model": model,
            "content": "stub",
            "timeout_s": timeout_s,
            "prompt_preview": prompt[:80],
        }

class QuestionSelector:
    def next_prompt(self, session_id: str, turn_index: int) -> str:
        if turn_index == 0:
            return "请先说说你会如何拆解这个问题。"
        return "继续，请说明你如何验证当前假设。"

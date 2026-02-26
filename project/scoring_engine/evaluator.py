# scoring_engine/evaluator.py
import os
from prompt.template_manager import load_templates_from_config, PromptTemplateManager

# 获取模板配置文件路径（相对于项目根目录）
config_path = os.path.join(os.path.dirname(__file__), '..', 'prompt', 'templates_config.json')
manager = load_templates_from_config(config_path)

def evaluate(question: str, answer: str) -> dict:
    # 获取主评分模板的最新版本
    template = manager.get_template("main_scoring")
    if not template:
        raise ValueError("主评分模板不存在")
    
    # 渲染模板，生成完整的 prompt
    prompt = template.render(question=question, answer=answer)
    
    # 调用模型（例如通过 qwen_model.py 或 dashscope_mod.py）
    from qwen_model import call_model  # 假设有一个 call_model 函数
    model_output = call_model(prompt)
    
    # 解析模型输出（假设输出是 JSON 字符串）
    import json
    result = json.loads(model_output)
    return result
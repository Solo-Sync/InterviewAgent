"""
简单测试脚本：验证 ChatTongyi 是否能连接到 LLM 服务并返回结果。

用法:
    set DASHSCOPE_API_KEY=your_key
    python -m tests.test_llm_connection

脚本会检查环境变量、尝试创建客户端并发送一个简短请求，最后打印结果。
"""
import os
import sys
from time import time
from langchain_community.chat_models import ChatTongyi
from langchain_core.messages import HumanMessage
import httpx


def test_connection():
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        print("环境变量 DASHSCOPE_API_KEY 未设置，无法测试。")
        return 2

    prompt = "请用一句话回答：pong"
    try:
        llm = ChatTongyi(
            api_key=api_key,
            model="qwen-plus",
            http_client=httpx.Client(trust_env=False)
        )
    except Exception as e:
        print(f"创建 ChatTongyi 失败: {e}")
        return 2

    print("发送测试请求...")
    start = time()
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        resp = response.content
    except Exception as e:
        print(f"请求抛出异常: {e}")
        return 3
    elapsed = time() - start

    if not resp:
        print(f"请求返回空响应（耗时 {elapsed:.2f}s） - 可能超时或网络错误")
        return 3

    print(f"收到响应（耗时 {elapsed:.2f}s）：")
    print(resp)
    return 0


if __name__ == "__main__":
    code = test_connection()
    if code == 0:
        print("LLM 连接测试成功。")
    else:
        print("LLM 连接测试失败，退出码：", code)
    sys.exit(code)


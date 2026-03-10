import pytest

from libs.llm_gateway.client import LLMGateway, LLMGatewayError, build_json_schema_response_format


def test_stub_provider_is_not_configured() -> None:
    gateway = LLMGateway(provider="stub")

    readiness = gateway.readiness()

    assert readiness.status == "not_configured"
    assert readiness.ready is False
    assert readiness.detail == "stub provider is configured"


def test_supported_provider_with_api_key_is_ready() -> None:
    gateway = LLMGateway(provider="openai", api_key="secret")

    readiness = gateway.readiness()

    assert readiness.status == "ready"
    assert readiness.ready is True
    assert readiness.detail is None


def test_supported_provider_without_api_key_is_not_configured() -> None:
    gateway = LLMGateway(provider="aliyun", api_key=None)

    readiness = gateway.readiness()

    assert readiness.status == "not_configured"
    assert readiness.ready is False
    assert readiness.detail == "missing API key for gateway provider"


def test_dashscope_endpoint_resolution() -> None:
    gateway = LLMGateway(provider="aliyun", base_url="https://dashscope.aliyuncs.com", api_key="k")
    assert (
        gateway._resolve_dashscope_endpoint()
        == "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    )

    gateway_with_api_v1 = LLMGateway(
        provider="dashscope",
        base_url="https://dashscope.aliyuncs.com/api/v1",
        api_key="k",
    )
    assert (
        gateway_with_api_v1._resolve_dashscope_endpoint()
        == "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    )


def test_dashscope_extracts_message_content() -> None:
    gateway = LLMGateway(provider="aliyun", api_key="k")
    expected = '{"dimension_scores":{"plan":1,"monitor":1,"evaluate":1,"adapt":1}}'
    payload = {
        "output": {
            "choices": [
                {
                    "message": {"content": expected}
                }
            ]
        }
    }
    assert gateway._extract_dashscope_content(payload) == expected


def test_dashscope_extracts_text_fallback() -> None:
    gateway = LLMGateway(provider="aliyun", api_key="k")
    payload = {"output": {"text": '{"dimension_scores":{"plan":2}}'}}
    assert gateway._extract_dashscope_content(payload) == '{"dimension_scores":{"plan":2}}'


def test_dashscope_extract_raises_on_invalid_payload() -> None:
    gateway = LLMGateway(provider="aliyun", api_key="k")
    with pytest.raises(LLMGatewayError):
        gateway._extract_dashscope_content({"output": {"choices": []}})


def test_openai_payload_includes_json_schema_response_format() -> None:
    gateway = LLMGateway(provider="openai", api_key="k")
    response_format = build_json_schema_response_format(
        name="demo_schema",
        schema={
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
            "additionalProperties": False,
        },
    )

    payload = gateway._build_openai_payload(
        model="qwen-plus",
        prompt="Return a value",
        system_prompt=None,
        response_format=response_format,
    )

    assert payload["response_format"]["type"] == "json_schema"
    assert payload["response_format"]["json_schema"]["name"] == "demo_schema"
    assert payload["messages"][0]["role"] == "system"


def test_dashscope_payload_includes_json_schema_response_format() -> None:
    gateway = LLMGateway(provider="aliyun", api_key="k")
    response_format = build_json_schema_response_format(
        name="demo_schema",
        schema={
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
            "additionalProperties": False,
        },
    )

    payload = gateway._build_dashscope_payload(
        model="qwen-plus",
        prompt="Return a value",
        system_prompt=None,
        response_format=response_format,
    )

    assert payload["parameters"]["result_format"] == "message"
    assert payload["parameters"]["response_format"]["type"] == "json_schema"
    assert payload["parameters"]["response_format"]["json_schema"]["name"] == "demo_schema"


def test_json_schema_response_extracts_parsed_payload() -> None:
    gateway = LLMGateway(provider="aliyun", api_key="k")
    response_format = build_json_schema_response_format(
        name="demo_schema",
        schema={
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
            "additionalProperties": False,
        },
    )

    parsed = gateway._maybe_extract_structured_payload('{"value":"ok"}', response_format)

    assert parsed == {"value": "ok"}

from __future__ import annotations

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
from typing import Any

import httpx

from libs.env_loader import load_project_env
from libs.observability import log_event
from libs.readiness import ReadinessProbe

_UNSET = object()
logger = logging.getLogger(__name__)


class LLMGatewayError(RuntimeError):
    pass


class LLMGateway:
    _ALIYUN_PROVIDERS = {"aliyun", "dashscope"}
    _SUPPORTED_PROVIDERS = {"stub", "openai", "openai_compatible", "aliyun", "dashscope"}

    def __init__(
        self,
        *,
        provider: str | None = None,
        base_url: str | None = None,
        api_key: str | None | object = _UNSET,
    ) -> None:
        load_project_env()
        self.provider = (provider or os.getenv("LLM_GATEWAY_PROVIDER", "stub")).lower()
        if self.provider in self._ALIYUN_PROVIDERS:
            self.base_url = (
                base_url
                or os.getenv("LLM_GATEWAY_BASE_URL")
                or os.getenv("DASHSCOPE_BASE_URL")
                or "https://dashscope.aliyuncs.com"
            )
        else:
            self.base_url = (
                base_url
                or os.getenv("LLM_GATEWAY_BASE_URL")
                or os.getenv("OPENAI_BASE_URL")
                or "https://api.openai.com"
            )
        if api_key is _UNSET:
            self.api_key = (
                os.getenv("LLM_GATEWAY_API_KEY")
                or os.getenv("DASHSCOPE_API_KEY")
                or os.getenv("OPENAI_API_KEY")
            )
        else:
            self.api_key = api_key
        self.workspace = os.getenv("DASHSCOPE_WORKSPACE")

    def readiness(self) -> ReadinessProbe:
        if self.provider == "stub":
            return ReadinessProbe(status="not_configured", detail="stub provider is configured")
        if self.provider not in self._SUPPORTED_PROVIDERS:
            return ReadinessProbe(
                status="unavailable",
                detail=f"unsupported gateway provider: {self.provider}",
            )
        if not self.api_key:
            return ReadinessProbe(
                status="not_configured",
                detail="missing API key for gateway provider",
            )
        return ReadinessProbe(status="ready")

    async def complete(self, model: str, prompt: str, timeout_s: float = 3.0) -> dict[str, Any]:
        call_started = perf_counter()
        log_event(
            logger,
            logging.INFO,
            "llm_gateway_call_started",
            provider=self.provider,
            model=model,
            timeout_s=timeout_s,
            prompt=prompt,
            prompt_chars=len(prompt),
        )
        if self.provider == "stub":
            result = {
                "model": model,
                "content": "stub",
                "provider": self.provider,
                "timeout_s": timeout_s,
                "prompt_preview": prompt[:80],
            }
            self._log_call_completed(
                model=model,
                timeout_s=timeout_s,
                started_at=call_started,
                content=result.get("content"),
                raw=result.get("raw"),
            )
            return result
        if self.provider in {"openai", "openai_compatible"}:
            try:
                result = await self._complete_openai(model, prompt, timeout_s=timeout_s)
            except Exception as exc:  # noqa: BLE001
                self._log_call_failed(
                    model=model,
                    timeout_s=timeout_s,
                    started_at=call_started,
                    exc=exc,
                )
                raise
            self._log_call_completed(
                model=model,
                timeout_s=timeout_s,
                started_at=call_started,
                content=result.get("content"),
                raw=result.get("raw"),
            )
            return result
        if self.provider in self._ALIYUN_PROVIDERS:
            try:
                result = await self._complete_dashscope(model, prompt, timeout_s=timeout_s)
            except Exception as exc:  # noqa: BLE001
                self._log_call_failed(
                    model=model,
                    timeout_s=timeout_s,
                    started_at=call_started,
                    exc=exc,
                )
                raise
            self._log_call_completed(
                model=model,
                timeout_s=timeout_s,
                started_at=call_started,
                content=result.get("content"),
                raw=result.get("raw"),
            )
            return result
        self._log_call_failed(
            model=model,
            timeout_s=timeout_s,
            started_at=call_started,
            exc=LLMGatewayError(f"unsupported gateway provider: {self.provider}"),
        )
        raise LLMGatewayError(f"unsupported gateway provider: {self.provider}")

    def complete_sync(self, model: str, prompt: str, timeout_s: float = 3.0) -> dict[str, Any]:
        coro = self.complete(model=model, prompt=prompt, timeout_s=timeout_s)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()

    async def _complete_openai(
        self,
        model: str,
        prompt: str,
        *,
        timeout_s: float,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise LLMGatewayError("missing API key for openai gateway provider")

        base = self.base_url.rstrip("/")
        endpoint = f"{base}/v1/chat/completions"
        payload = {
            "model": model,
            "temperature": 0.0,
            "messages": [
                {"role": "system", "content": "You are a strict JSON output scorer."},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                response = await client.post(endpoint, json=payload, headers=headers)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMGatewayError(f"upstream llm call failed: {exc}") from exc

        data = response.json()
        content = self._extract_content(data)
        return {
            "model": model,
            "content": content,
            "provider": self.provider,
            "timeout_s": timeout_s,
            "raw": data,
        }

    async def _complete_dashscope(
        self,
        model: str,
        prompt: str,
        *,
        timeout_s: float,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise LLMGatewayError("missing API key for aliyun dashscope gateway provider")

        endpoint = self._resolve_dashscope_endpoint()
        payload = {
            "model": model,
            "input": {
                "messages": [
                    {"role": "system", "content": "You are a strict JSON output scorer."},
                    {"role": "user", "content": prompt},
                ]
            },
            "parameters": {"result_format": "message"},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.workspace:
            headers["X-DashScope-WorkSpace"] = self.workspace

        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                response = await client.post(endpoint, json=payload, headers=headers)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMGatewayError(f"upstream llm call failed: {exc}") from exc

        data = response.json()
        content = self._extract_dashscope_content(data)
        return {
            "model": model,
            "content": content,
            "provider": self.provider,
            "timeout_s": timeout_s,
            "raw": data,
        }

    def _extract_content(self, payload: dict[str, Any]) -> str:
        choices = payload.get("choices") or []
        if not choices:
            raise LLMGatewayError("llm response missing choices")

        message = (choices[0] or {}).get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_parts.append(str(part.get("text", "")))
            if text_parts:
                return "".join(text_parts)
        raise LLMGatewayError("llm response missing text content")

    def _resolve_dashscope_endpoint(self) -> str:
        base = self.base_url.rstrip("/")
        if base.endswith("/api/v1/services/aigc/text-generation/generation"):
            return base
        if base.endswith("/api/v1"):
            return f"{base}/services/aigc/text-generation/generation"
        return f"{base}/api/v1/services/aigc/text-generation/generation"

    def _extract_dashscope_content(self, payload: dict[str, Any]) -> str:
        output = payload.get("output")
        if not isinstance(output, dict):
            raise LLMGatewayError("dashscope response missing output")

        choices = output.get("choices")
        if isinstance(choices, list) and choices:
            message = (choices[0] or {}).get("message") or {}
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content
            if isinstance(content, list):
                text_parts = []
                for item in content:
                    if isinstance(item, str):
                        text_parts.append(item)
                    elif isinstance(item, dict):
                        maybe_text = item.get("text")
                        if isinstance(maybe_text, str):
                            text_parts.append(maybe_text)
                merged = "".join(text_parts).strip()
                if merged:
                    return merged

        text = output.get("text")
        if isinstance(text, str) and text.strip():
            return text

        raise LLMGatewayError("dashscope response missing text content")

    def _log_call_completed(
        self,
        *,
        model: str,
        timeout_s: float,
        started_at: float,
        content: Any,
        raw: Any,
    ) -> None:
        latency_ms = round((perf_counter() - started_at) * 1000, 3)
        log_event(
            logger,
            logging.INFO,
            "llm_gateway_call_completed",
            provider=self.provider,
            model=model,
            timeout_s=timeout_s,
            latency_ms=latency_ms,
            content=content,
            raw=raw,
        )

    def _log_call_failed(
        self,
        *,
        model: str,
        timeout_s: float,
        started_at: float,
        exc: Exception,
    ) -> None:
        latency_ms = round((perf_counter() - started_at) * 1000, 3)
        log_event(
            logger,
            logging.ERROR,
            "llm_gateway_call_failed",
            provider=self.provider,
            model=model,
            timeout_s=timeout_s,
            latency_ms=latency_ms,
            error_type=exc.__class__.__name__,
            error_message=str(exc),
        )

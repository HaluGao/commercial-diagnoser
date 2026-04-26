from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import requests


OPENAI_COMPATIBLE = "openai_compatible"
GEMINI_NATIVE = "gemini_native"


@dataclass
class ProviderConfig:
    provider_name: str
    protocol: str
    base_url: str
    api_key: str
    model: str
    timeout_seconds: int = 240


@dataclass
class ValidationDetails:
    ok: bool
    indicator: str
    summary: str
    diagnostics: list[dict[str, Any]]


class ApiYiProvider:
    def __init__(self, config: ProviderConfig):
        self.config = config

    def validate(self) -> ValidationDetails:
        if not self.config.api_key:
            return ValidationDetails(
                ok=False,
                indicator="未配置 API Key",
                summary="请先填写 API Key。",
                diagnostics=[],
            )

        try:
            if self.config.protocol == GEMINI_NATIVE:
                response, strategy_name = self._request_gemini(
                    payload={
                        "contents": [{"role": "user", "parts": [{"text": "ping"}]}],
                        "generationConfig": {"maxOutputTokens": 1},
                    },
                    timeout=10,
                )
                diagnostics = [
                    {
                        "protocol": self.config.protocol,
                        "model": self.config.model,
                        "strategy": strategy_name,
                        "status_code": response.status_code,
                        "response_preview": self._response_preview(response),
                    }
                ]
            else:
                response = requests.post(
                    f"{self._openai_base_url()}/chat/completions",
                    headers=self._openai_headers(),
                    json={
                        "model": self.config.model,
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 1,
                        "temperature": 0,
                    },
                    timeout=10,
                )
                diagnostics = [
                    {
                        "protocol": self.config.protocol,
                        "model": self.config.model,
                        "strategy": "bearer_chat_probe",
                        "status_code": response.status_code,
                        "response_preview": self._response_preview(response),
                    }
                ]

            if response.status_code == 200:
                return ValidationDetails(
                    ok=True,
                    indicator="🟢",
                    summary="API 通道可用。",
                    diagnostics=diagnostics,
                )
            if response.status_code == 401:
                return ValidationDetails(
                    ok=False,
                    indicator="🔴 [401 鉴权失败，请检查 API易 key / protocol]",
                    summary="当前 key、模型或协议未通过鉴权。优先建议先试 gemini-2.5-flash，若仍失败再切 openai_compatible + gpt-5.4-mini。",
                    diagnostics=diagnostics,
                )
            if response.status_code == 404:
                return ValidationDetails(
                    ok=False,
                    indicator="🔴 [404 端点不匹配，请切换 protocol]",
                    summary="当前 base URL 下没有命中对应协议端点，建议切换 protocol 再试。",
                    diagnostics=diagnostics,
                )
            if response.status_code == 403:
                summary = "当前 API Key 可连通，但无权使用这个模型。请先换低成本模型试跑，或去 API易 控制台检查该令牌是否设置了可用模型白名单。"
                preview = diagnostics[0]["response_preview"] if diagnostics else ""
                if "无权使用模型" in preview or "Model not allowed" in preview:
                    summary = "当前 API Key 没有这个模型的使用权限。按 API易 文档，通常是令牌设置了可用模型白名单，或白名单未包含该正式模型名。"
                return ValidationDetails(
                    ok=False,
                    indicator="🟡 [403 当前模型无权限]",
                    summary=summary,
                    diagnostics=diagnostics,
                )
            return ValidationDetails(
                ok=False,
                indicator=f"🔴 [{response.status_code}]",
                summary="接口有返回，但未通过预检。可以展开连接诊断查看返回片段。",
                diagnostics=diagnostics,
            )
        except Exception as exc:
            return ValidationDetails(
                ok=False,
                indicator="🔴 连接失败",
                summary=f"本地到 API易 的请求未成功：{exc}",
                diagnostics=[],
            )

    def generate_report(self, prompt: str, media_items: list[dict[str, str]]) -> str:
        if self.config.protocol == GEMINI_NATIVE:
            return self._generate_with_gemini(prompt, media_items)
        return self._generate_with_openai(prompt, media_items)

    def _generate_with_gemini(self, prompt: str, media_items: list[dict[str, str]]) -> str:
        parts: list[dict[str, Any]] = [{"text": prompt}]
        for item in media_items:
            parts.append(
                {
                    "inline_data": {
                        "mime_type": item["mime_type"],
                        "data": item["data"],
                    }
                }
            )

        payload = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"temperature": 0.1},
        }

        for attempt in range(6):
            response, strategy_name = self._request_gemini(
                payload=payload,
                timeout=self.config.timeout_seconds,
            )
            if response.status_code == 200:
                data = response.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            if response.status_code in {429, 500, 502, 503, 504}:
                time.sleep(min(40, 3 * (attempt + 1)))
                continue
            raise RuntimeError(
                f"Gemini native request failed via {strategy_name}: HTTP {response.status_code} {self._response_preview(response)}"
            )

        raise RuntimeError("Gemini native request failed after retries.")

    def _generate_with_openai(self, prompt: str, media_items: list[dict[str, str]]) -> str:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for item in media_items:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{item['mime_type']};base64,{item['data']}"
                    },
                }
            )

        payload = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": content}],
            "temperature": 0.1,
        }

        for attempt in range(6):
            response = requests.post(
                f"{self._openai_base_url()}/chat/completions",
                headers=self._openai_headers(),
                json=payload,
                timeout=self.config.timeout_seconds,
            )
            if response.status_code == 200:
                data = response.json()
                message = data["choices"][0]["message"]["content"]
                if isinstance(message, str):
                    return message
                if isinstance(message, list):
                    return "\n".join(
                        part.get("text", "") for part in message if isinstance(part, dict)
                    )
                return json.dumps(message, ensure_ascii=False)
            if response.status_code in {429, 500, 502, 503, 504}:
                time.sleep(min(40, 3 * (attempt + 1)))
                continue
            raise RuntimeError(
                f"OpenAI compatible request failed: HTTP {response.status_code} {self._response_preview(response)}"
            )

        raise RuntimeError("OpenAI compatible request failed after retries.")

    def _gemini_endpoint(self) -> str:
        base_url = self._gemini_base_url()
        return f"{base_url}/v1beta/models/{self.config.model}:generateContent?key={self.config.api_key}"

    def _gemini_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }

    def _openai_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }

    def _request_gemini(self, payload: dict[str, Any], timeout: int) -> tuple[requests.Response, str]:
        base_url = self._gemini_base_url()
        url_with_query = f"{base_url}/v1beta/models/{self.config.model}:generateContent?key={self.config.api_key}"
        url_without_query = f"{base_url}/v1beta/models/{self.config.model}:generateContent"

        auth_strategies = [
            {
                "name": "query_key_only",
                "url": url_with_query,
                "headers": {"Content-Type": "application/json"},
            },
            {
                "name": "bearer_only",
                "url": url_without_query,
                "headers": self._gemini_headers(),
            },
            {
                "name": "query_key_and_bearer",
                "url": url_with_query,
                "headers": self._gemini_headers(),
            },
        ]

        last_response: requests.Response | None = None
        last_strategy = "unknown"
        for strategy in auth_strategies:
            response = requests.post(
                strategy["url"],
                headers=strategy["headers"],
                json=payload,
                timeout=timeout,
            )
            last_response = response
            last_strategy = str(strategy["name"])
            if response.status_code != 401:
                return response, last_strategy

        assert last_response is not None
        return last_response, last_strategy

    def _response_preview(self, response: requests.Response) -> str:
        try:
            data = response.json()
            return json.dumps(data, ensure_ascii=False)[:500]
        except Exception:
            return response.text[:500]

    def _openai_base_url(self) -> str:
        base_url = self.config.base_url.rstrip("/")
        if base_url.endswith("/v1"):
            return base_url
        return f"{base_url}/v1"

    def _gemini_base_url(self) -> str:
        base_url = self.config.base_url.rstrip("/")
        if base_url.endswith("/v1"):
            return base_url[:-3]
        return base_url

"""OpenAI-compatible chat completions backend (works for OpenAI, OpenRouter,
vLLM, LM Studio, and most local servers exposing /v1/chat/completions)."""

from __future__ import annotations

import json
from typing import Any, Optional

import httpx

from wamah.runtimes import BackendResponse


class OpenAICompatBackend:
    name = "openai"

    def __init__(self, base_url: str, api_key: str = "", model: str = "gpt-4o-mini",
                 timeout: float = 120.0, extra_headers: Optional[dict[str, str]] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.extra_headers = extra_headers or {}

    def begin_item(self, item_id: str) -> None:  # stateless
        return None

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> BackendResponse:
        payload: dict[str, Any] = {"model": self.model, "messages": messages}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        headers = {"Content-Type": "application/json", **self.extra_headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        url = f"{self.base_url}/chat/completions"
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:  # network / http errors become graded ERRORs
            return BackendResponse(error=f"{type(exc).__name__}: {exc}")
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        tool_calls = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") or {}
            tool_calls.append({
                "id": tc.get("id", "call_1"),
                "type": "function",
                "function": {"name": fn.get("name", ""),
                             "arguments": fn.get("arguments", "{}")},
            })
        return BackendResponse(content=msg.get("content") or "", tool_calls=tool_calls, raw=data)

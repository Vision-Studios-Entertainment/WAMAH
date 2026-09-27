"""Anthropic Messages API backend."""

from __future__ import annotations

from typing import Any, Optional

import httpx

from wamah.runtimes import BackendResponse


class AnthropicBackend:
    name = "anthropic"

    def __init__(self, base_url: str = "https://api.anthropic.com", api_key: str = "",
                 model: str = "claude-sonnet-4-5", timeout: float = 120.0,
                 max_tokens: int = 1500):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_tokens = max_tokens

    def begin_item(self, item_id: str) -> None:
        return None

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> BackendResponse:
        system_parts = [m["content"] for m in messages if m.get("role") == "system"]
        chat = []
        for m in messages:
            role = m.get("role")
            if role == "system":
                continue
            if role == "tool":
                # approximate tool results as user turns (no tool chain kept)
                chat.append({"role": "user", "content": f"[tool result] {m.get('content', '')}"})
                continue
            if role not in ("user", "assistant"):
                role = "user"
            chat.append({"role": role, "content": m.get("content", "")})
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": chat,
        }
        if system_parts:
            payload["system"] = "\n".join(system_parts)
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        try:
            resp = httpx.post(f"{self.base_url}/v1/messages", json=payload,
                              headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            return BackendResponse(error=f"{type(exc).__name__}: {exc}")
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        return BackendResponse(content=text, raw=data)

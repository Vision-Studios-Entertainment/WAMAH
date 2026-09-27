"""Ollama /api/chat backend for local open-weight models."""

from __future__ import annotations

from typing import Any, Optional

import httpx

from wamah.runtimes import BackendResponse


class OllamaBackend:
    name = "ollama"

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.1",
                 timeout: float = 180.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def begin_item(self, item_id: str) -> None:
        return None

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> BackendResponse:
        clean = []
        for m in messages:
            role = m.get("role", "user")
            if role == "tool":
                role = "user"
            if role not in ("system", "user", "assistant"):
                role = "user"
            clean.append({"role": role, "content": m.get("content", "")})
        payload: dict[str, Any] = {"model": self.model, "messages": clean, "stream": False}
        if tools:
            payload["tools"] = tools
        try:
            resp = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            return BackendResponse(error=f"{type(exc).__name__}: {exc}")
        msg = data.get("message") or {}
        return BackendResponse(content=msg.get("content") or "", raw=data)

"""Backend protocol shared by every runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable


@dataclass
class BackendResponse:
    content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    executed_actions: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@runtime_checkable
class ChatBackend(Protocol):
    name: str

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> BackendResponse: ...

    def begin_item(self, item_id: str) -> None:
        """Optional hook: reset per-item state (used by the transcript backend)."""


def system_message(content: str) -> dict[str, Any]:
    return {"role": "system", "content": content}


def user_message(content: str) -> dict[str, Any]:
    return {"role": "user", "content": content}


def assistant_message(content: str, tool_calls: Optional[list[dict[str, Any]]] = None) -> dict[str, Any]:
    msg: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return msg


def tool_message(content: str, tool_call_id: str = "wamah-poison") -> dict[str, Any]:
    return {"role": "tool", "content": content, "tool_call_id": tool_call_id}

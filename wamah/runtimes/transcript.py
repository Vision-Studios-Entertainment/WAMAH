"""Offline replay backend: feeds scripted responses from a JSON fixture.

Fixture shape:
{
  "S1-Q-H01-T01": ["turn one reply", "turn two reply"],
  "default": ["..."]
}
Calls are consumed in order per item; when exhausted the last entry repeats.
This keeps CI and local demos fully offline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from wamah.runtimes import BackendResponse


class TranscriptBackend:
    name = "transcript"

    def __init__(self, fixture_path: str | Path | None = None,
                 responses: Optional[dict[str, list[str]]] = None):
        self._data: dict[str, list[str]] = dict(responses or {})
        if fixture_path:
            self._data.update(json.loads(Path(fixture_path).read_text(encoding="utf-8")))
        self._current: str | None = None
        self._cursor = 0

    def begin_item(self, item_id: str) -> None:
        self._current = item_id
        self._cursor = 0

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> BackendResponse:
        script = self._data.get(self._current or "", self._data.get("default", [""]))
        if not script:
            script = [""]
        idx = min(self._cursor, len(script) - 1)
        self._cursor += 1
        text = script[idx]
        # convention: a fixture line starting with "TOOLCALL:" makes the
        # transcript simulate an agentic tool invocation
        if text.startswith("TOOLCALL:"):
            try:
                payload = json.loads(text[len("TOOLCALL:"):])
            except json.JSONDecodeError:
                payload = {"name": "unknown", "arguments": {}}
            return BackendResponse(
                content="",
                tool_calls=[{
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": payload.get("name", "unknown"),
                                 "arguments": json.dumps(payload.get("arguments", {}))},
                }],
                raw={"fixture": True},
            )
        return BackendResponse(content=text, raw={"fixture": True})

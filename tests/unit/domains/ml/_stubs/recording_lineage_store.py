"""Recording stub :class:`LineageStore` for tests."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn_ml.lineage_store import LineageStore


class RecordingLineageStore(LineageStore):
    def __init__(self) -> None:
        self.events: list[tuple[str, Mapping[str, Any]]] = []
        self.fetches: list[str] = []
        self.closed: bool = False

    async def log_event(
        self, event_type: str, payload: Mapping[str, Any]
    ) -> None:
        self.events.append((event_type, dict(payload)))

    async def fetch_lineage(self, model_id: str) -> Mapping[str, Any]:
        self.fetches.append(model_id)
        return {"model_id": model_id, "events": []}

    async def close(self) -> None:
        self.closed = True

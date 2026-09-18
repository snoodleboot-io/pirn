"""``EventsSnapshot`` — one day of clickstream events from the analytics store.

Part of the ``examples.data_pipeline.complex_analytics`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EventsSnapshot:
    date: str
    rows: list[dict]

    @property
    def session_count(self) -> int:
        return len({r["session_id"] for r in self.rows})

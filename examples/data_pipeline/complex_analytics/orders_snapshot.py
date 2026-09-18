"""``OrdersSnapshot`` — one day of order rows from the transactional database.

Part of the ``examples.data_pipeline.complex_analytics`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OrdersSnapshot:
    date: str
    rows: list[dict]

    @property
    def revenue(self) -> float:
        return sum(r["amount"] for r in self.rows)

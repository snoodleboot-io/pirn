"""``Notification`` — the dispatch notice sent once fulfillment completes.

Part of the ``examples.pipeline_composition.sub_tapestry`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Notification:
    order_id: str
    channel: str
    message: str
    sent: bool

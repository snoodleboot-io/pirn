"""``InventoryCheck`` — result of the inner inventory lookup.

Part of the ``examples.pipeline_composition.sub_tapestry`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class InventoryCheck:
    available: bool
    items_found: list[str]
    items_missing: list[str]

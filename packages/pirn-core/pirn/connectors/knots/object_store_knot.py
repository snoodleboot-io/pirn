"""``ObjectStoreKnot`` — vending Knot for an :class:`ObjectStore`.

Wraps an externally-constructed store so it participates in the pirn graph
with full lineage. Consumers receive the resolved store value in their
``process()`` calls.

Algorithm:
    1. Accept the store value (resolved by the framework from an upstream
       Knot or a scalar passed at pipeline-build time).
    2. Return it unchanged so downstream Knots receive the store instance.


References:
    - :class:`pirn.connectors.object_store.ObjectStore`
"""

from __future__ import annotations

from typing import Any

from pirn.connectors.object_store import ObjectStore
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class ObjectStoreKnot(Knot):
    def __init__(self, *, store: Knot | ObjectStore, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(store=store, _config=_config, **kwargs)

    async def process(self, store: ObjectStore, **_: Any) -> ObjectStore:
        return store

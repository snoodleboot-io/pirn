"""``ObjectStoreListSource`` — a pirn :class:`Source` that lists keys under
a prefix in any :class:`ObjectStore` backend.

Algorithm:
    1. Validate that ``store`` is an :class:`ObjectStore` and ``prefix``
       is a string.
    2. Call ``await store.list(prefix)`` to obtain an async iterator of keys.
    3. Collect all keys into a list and return it in lexicographic order.


References:
    - :class:`pirn.domains.connectors.object_store.ObjectStore`
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.knots.object_store_knot import ObjectStoreKnot
from pirn.domains.connectors.object_store import ObjectStore
from pirn.nodes.source import Source


class ObjectStoreListSource(Source):
    """Source that lists keys under a fixed ``prefix`` in lexicographic order."""

    def __init__(
        self,
        *,
        store: ObjectStoreKnot,
        prefix: Knot | str = "",
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(store=store, prefix=prefix, _config=_config, **kwargs)

    async def process(self, store: ObjectStore, prefix: str = "", **_: Any) -> list[str]:
        """List all object-store keys under the configured prefix and return them in order.

        Args:
            store: The object store to list keys from.
            prefix: The key prefix to filter by.

        Returns:
            A list of object-store key strings whose names begin with the configured prefix.

        Raises:
            TypeError: If store is not an ObjectStore or prefix is not a string.
        """
        if not isinstance(store, ObjectStore):
            raise TypeError(
                f"ObjectStoreListSource: store must be an ObjectStore, got {type(store).__name__}"
            )
        if not isinstance(prefix, str):
            raise TypeError("ObjectStoreListSource: prefix must be a string")
        keys: list[str] = []
        async for key in await store.list(prefix):
            keys.append(key)
        return keys

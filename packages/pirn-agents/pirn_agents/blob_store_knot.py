"""``BlobStoreKnot`` — vending Knot for a pooled :class:`BlobStore`.

Vends the F16-S4 object/blob storage connector once per run (AD-3): the
provider-neutral :class:`~pirn_agents.connectors.blob_store.BlobStore` (local FS
or S3-compatible) is constructed once and passed through the graph unchanged, so
any pooled backend client it holds is reused for the whole run. ``process``
validates the vended value with an ``isinstance`` check so a mis-wired pipeline
fails loudly at the vend site.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.connectors.blob_store import BlobStore


class BlobStoreKnot(Knot):
    """Vending Knot that passes a pooled :class:`BlobStore` through the graph."""

    def __init__(self, *, store: Knot | BlobStore, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(store=store, _config=_config, **kwargs)

    async def process(self, store: BlobStore, **_: Any) -> BlobStore:
        """Return the blob store unchanged after validating its type.

        Raises:
            TypeError: If ``store`` is not a :class:`BlobStore`.
        """
        if not isinstance(store, BlobStore):
            raise TypeError(f"BlobStoreKnot: expected a BlobStore, got {type(store).__name__}")
        return store

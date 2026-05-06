"""Interface for ML lineage / model-registry stores.

Concrete implementations (MLflow, Weights & Biases, custom catalogs)
inherit from :class:`LineageStore` and override every method. Pirn's
content-addressing treats lineage stores as opaque (see
:class:`pirn.core.pirn_opaque_value.PirnOpaqueValue`); the default
identity-keyed serialiser keeps cache stable without descending into
live registry state.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class LineageStore(PirnOpaqueValue):
    """Interface every ML lineage / registry implementation must satisfy."""

    async def log_event(self, event_type: str, payload: Mapping[str, Any]) -> None:
        """Record a lineage event (training, evaluation, deployment)."""
        raise NotImplementedError(f"{type(self).__name__} must implement log_event()")

    async def fetch_lineage(self, model_id: str) -> Mapping[str, Any]:
        """Return the recorded lineage chain for ``model_id``."""
        raise NotImplementedError(f"{type(self).__name__} must implement fetch_lineage()")

    async def close(self) -> None:
        """Close the store and release any underlying resources."""
        raise NotImplementedError(f"{type(self).__name__} must implement close()")

    def _clear_credentials(self) -> None:
        """Drop the in-memory credential reference held by the store.

        Concrete stores should call this from ``close()`` after tearing
        down the live registry client. It nulls ``self._config`` so any
        credential strings (API keys, tokens) become garbage-collectable
        as soon as the caller drops the store reference.
        """
        self._config = None

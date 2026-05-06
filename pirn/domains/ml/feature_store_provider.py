"""Interface for ML feature stores (Feast, Tecton, custom catalogs).

Concrete implementations inherit from :class:`FeatureStoreProvider` and
override every method. Pirn treats providers as opaque
(see :class:`pirn.core.pirn_opaque_value.PirnOpaqueValue`); the default
identity-keyed serialiser keeps content-addressing cache stable without
descending into live store state.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class FeatureStoreProvider(PirnOpaqueValue):
    """Interface every feature-store implementation must satisfy."""

    async def get_features(
        self,
        entity_keys: Sequence[Mapping[str, Any]],
        feature_names: Sequence[str],
    ) -> list[Mapping[str, Any]]:
        """Return one feature row per entity key in ``entity_keys`` order."""
        raise NotImplementedError(f"{type(self).__name__} must implement get_features()")

    async def write_features(self, features: Iterable[Mapping[str, Any]]) -> int:
        """Persist computed feature rows. Returns the number written."""
        raise NotImplementedError(f"{type(self).__name__} must implement write_features()")

    async def close(self) -> None:
        """Close the provider and release any underlying resources."""
        raise NotImplementedError(f"{type(self).__name__} must implement close()")

    def _clear_credentials(self) -> None:
        """Drop the in-memory credential reference held by the provider."""
        self._config = None

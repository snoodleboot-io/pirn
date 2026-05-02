"""Recording stub :class:`FeatureStoreProvider` for tests."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from pirn.domains.ml.feature_store_provider import FeatureStoreProvider


class RecordingFeatureStoreProvider(FeatureStoreProvider):
    def __init__(self) -> None:
        self.written: list[dict[str, Any]] = []
        self.requested: list[tuple[list[Mapping[str, Any]], list[str]]] = []
        self.closed: bool = False

    async def get_features(
        self,
        entity_keys: Sequence[Mapping[str, Any]],
        feature_names: Sequence[str],
    ) -> list[Mapping[str, Any]]:
        self.requested.append((list(entity_keys), list(feature_names)))
        return [dict(key) for key in entity_keys]

    async def write_features(
        self, features: Iterable[Mapping[str, Any]]
    ) -> int:
        rows = [dict(row) for row in features]
        self.written.extend(rows)
        return len(rows)

    async def close(self) -> None:
        self.closed = True

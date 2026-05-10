"""``DataSplitPayload`` — SplitManifest metadata bundled with SplitArrays."""

from __future__ import annotations

from pirn.core.payload import Payload
from pirn.domains.ml.types.split_arrays import SplitArrays
from pirn.domains.ml.types.split_manifest import SplitManifest


class DataSplitPayload(Payload[SplitManifest, SplitArrays]):
    @property
    def manifest(self) -> SplitManifest:
        return self._metadata

    @property
    def arrays(self) -> SplitArrays:
        return self._data

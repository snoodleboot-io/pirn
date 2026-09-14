"""``DataSplitPayload`` — SplitManifest metadata bundled with SplitArrays."""

from __future__ import annotations

from pirn.core.payload import Payload

from pirn_ml.types.split_arrays import SplitArrays
from pirn_ml.types.split_manifest import SplitManifest


class DataSplitPayload(Payload[SplitManifest, SplitArrays]):
    """``metadata`` is the :class:`SplitManifest`; ``data`` is the ``SplitArrays``."""

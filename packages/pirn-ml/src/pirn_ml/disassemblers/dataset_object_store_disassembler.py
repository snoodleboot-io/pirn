"""``DatasetObjectStoreDisassembler`` — serialise a :class:`DatasetPayload` to numpy npz bytes.

Sits between domain knots that produce a :class:`DatasetPayload` and an
upstream object-store write connector that consumes ``bytes``.

Algorithm:
    1. Receive ``payload`` (:class:`DatasetPayload`).
    2. Validate type.
    3. Serialise :class:`MLFeatures` arrays via ``np.savez`` to an in-memory buffer.
    4. Return the buffer contents as ``bytes``.
    5. Serialisation runs on a thread to avoid blocking the event loop.

Math:
    No numeric transformation.  The feature matrix is stored verbatim:
        bytes = np.savez({feature_matrix: X, target_vector: y})
    where X has shape (n_samples, n_features) and y has shape (n_samples,).

References:
    - Harris, C.R. et al. (2020). "Array programming with NumPy." *Nature*, 585, 357-362.
"""

from __future__ import annotations

import asyncio
import io
from typing import Any

import numpy as np
from pirn.core.disassembler import Disassembler
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_ml.types.dataset_payload import DatasetPayload


def _serialize(payload: DatasetPayload) -> bytes:
    buf = io.BytesIO()
    features = payload.features
    arrays: dict[str, Any] = {"feature_matrix": features.feature_matrix}
    if features.target_vector is not None:
        arrays["target_vector"] = features.target_vector
    np.savez(buf, **arrays)
    return buf.getvalue()


class DatasetObjectStoreDisassembler(Disassembler):
    """Serialise a :class:`DatasetPayload` to numpy npz bytes for object-store persistence.

    Receives a typed :class:`DatasetPayload` and serialises its :class:`MLFeatures`
    arrays to ``bytes`` via ``np.savez``. Performs no I/O.
    """

    def __init__(
        self,
        *,
        payload: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(payload=payload, _config=_config, **kwargs)

    async def process(
        self,
        payload: DatasetPayload,
        **_: Any,
    ) -> bytes:
        """Serialise a :class:`DatasetPayload` to npz ``bytes``.

        Args:
            payload: The dataset payload to serialise.

        Returns:
            ``bytes`` produced by ``np.savez`` containing ``feature_matrix``
            and optionally ``target_vector``.

        Raises:
            TypeError: If ``payload`` is not a :class:`DatasetPayload`.
        """
        if not isinstance(payload, DatasetPayload):
            raise TypeError(
                f"DatasetObjectStoreDisassembler: payload must be DatasetPayload, "
                f"got {type(payload).__name__}"
            )
        return await asyncio.to_thread(_serialize, payload)

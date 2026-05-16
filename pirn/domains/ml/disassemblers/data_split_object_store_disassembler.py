"""``DataSplitObjectStoreDisassembler`` — serialise a :class:`DataSplitPayload` to numpy npz bytes.

Sits between domain knots that produce a :class:`DataSplitPayload` and an
upstream object-store write connector that consumes ``bytes``.

Algorithm:
    1. Receive ``payload`` (:class:`DataSplitPayload`).
    2. Validate type.
    3. Serialise all :class:`SplitArrays` arrays via ``np.savez`` to an in-memory buffer.
    4. Return the buffer contents as ``bytes``.
    5. Serialisation runs on a thread to avoid blocking the event loop.

Math:
    No numeric transformation.  Split arrays are stored verbatim:
        bytes = np.savez({X_train, X_test, y_train?, y_test?})
    where X_train has shape (n_train, n_features), X_test (n_test, n_features).

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
from pirn.domains.ml.types.data_split_payload import DataSplitPayload


def _serialize(payload: DataSplitPayload) -> bytes:
    buf = io.BytesIO()
    arrays = payload.arrays
    named: dict[str, Any] = {
        "X_train": arrays.X_train,
        "X_test": arrays.X_test,
    }
    if arrays.y_train is not None:
        named["y_train"] = arrays.y_train
    if arrays.y_test is not None:
        named["y_test"] = arrays.y_test
    np.savez(buf, **named)
    return buf.getvalue()


class DataSplitObjectStoreDisassembler(Disassembler):
    """Serialise a :class:`DataSplitPayload` to numpy npz bytes for object-store persistence.

    Receives a typed :class:`DataSplitPayload` and serialises all :class:`SplitArrays`
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
        payload: DataSplitPayload,
        **_: Any,
    ) -> bytes:
        """Serialise a :class:`DataSplitPayload` to npz ``bytes``.

        Args:
            payload: The data split payload to serialise.

        Returns:
            ``bytes`` produced by ``np.savez`` containing ``X_train``, ``X_test``,
            and optionally ``y_train``, ``y_test``.

        Raises:
            TypeError: If ``payload`` is not a :class:`DataSplitPayload`.
        """
        if not isinstance(payload, DataSplitPayload):
            raise TypeError(
                f"DataSplitObjectStoreDisassembler: payload must be DataSplitPayload, "
                f"got {type(payload).__name__}"
            )
        return await asyncio.to_thread(_serialize, payload)

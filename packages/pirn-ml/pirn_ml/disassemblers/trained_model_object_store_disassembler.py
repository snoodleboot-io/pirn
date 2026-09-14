# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
"""``TrainedModelObjectStoreDisassembler`` — serialise a :class:`TrainedModelPayload` to raw bytes.

Sits between domain knots that produce a :class:`TrainedModelPayload` and an
upstream object-store write connector that consumes ``bytes``.

Algorithm:
    1. Receive ``payload`` (:class:`TrainedModelPayload`).
    2. Validate type.
    3. Serialise the :class:`FittedEstimator` via ``joblib.dump`` to an in-memory buffer.
    4. Return the buffer contents as ``bytes``.
    5. Serialisation runs on a thread to avoid blocking the event loop.

Math:
    No numeric transformation.  Identity mapping on the estimator object:
        bytes = joblib.dump(estimator)  ≡  serialise(estimator)
    Output size: |bytes| = f(estimator complexity); no closed-form bound.

References:
    - Joblib contributors (2008-). *joblib*. https://joblib.readthedocs.io/
"""

from __future__ import annotations

import asyncio
import io
from typing import Any

from pirn.core.disassembler import Disassembler
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.optional_dependency import OptionalDependency

from pirn_ml.types.trained_model_payload import TrainedModelPayload


class TrainedModelObjectStoreDisassembler(Disassembler):
    """Serialise a :class:`TrainedModelPayload` to raw bytes for object-store persistence.

    Receives a typed :class:`TrainedModelPayload` and serialises its
    :class:`FittedEstimator` to ``bytes`` via ``joblib``. Performs no I/O.
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
        payload: TrainedModelPayload,
        **_: Any,
    ) -> bytes:
        """Serialise a :class:`TrainedModelPayload` to ``bytes``.

        Args:
            payload: The trained model payload to serialise.

        Returns:
            ``bytes`` produced by ``joblib.dump`` of the underlying estimator.

        Raises:
            TypeError: If ``payload`` is not a :class:`TrainedModelPayload`.
        """
        if not isinstance(payload, TrainedModelPayload):
            raise TypeError(
                f"TrainedModelObjectStoreDisassembler: payload must be TrainedModelPayload, "
                f"got {type(payload).__name__}"
            )
        return await asyncio.to_thread(TrainedModelObjectStoreDisassembler._serialize, payload)

    @staticmethod
    def _serialize(payload: TrainedModelPayload) -> bytes:
        joblib = OptionalDependency.require("joblib", extra="ml", package="pirn-ml")
        buf = io.BytesIO()
        joblib.dump(payload.estimator.estimator, buf)
        return buf.getvalue()

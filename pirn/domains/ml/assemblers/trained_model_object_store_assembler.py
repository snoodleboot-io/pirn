"""``TrainedModelObjectStoreAssembler`` — assemble a :class:`TrainedModelPayload` from raw model bytes.

Sits between an object-store read connector (which produces ``bytes``) and
downstream domain knots that consume :class:`~pirn.domains.ml.types.trained_model_payload.TrainedModelPayload`.

Algorithm:
    1. Receive ``body`` (serialised model bytes) and ``algorithm`` (str).
    2. Validate types and values.
    3. Deserialise the estimator via ``joblib.load``; fall back to ``pickle.loads`` on failure.
    4. Build a :class:`ModelManifest` from the estimator's attributes.
    5. Return a :class:`TrainedModelPayload` carrying the manifest and estimator.
    6. Deserialisation runs on a thread to avoid blocking the event loop.

Math:
    No numeric transformation.  Identity mapping on the byte stream:
        TrainedModelPayload = deserialise(body)
    model_id = algorithm + "_" + timestamp (UTC, YYYYmmddTHHMMSS)

References:
    - Joblib contributors (2008-). *joblib*. https://joblib.readthedocs.io/
"""

from __future__ import annotations

import asyncio
import io
import pickle
from datetime import UTC, datetime
from typing import Any

import joblib

from pirn.core.assembler import Assembler
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.ml.types.fitted_estimator import FittedEstimator
from pirn.domains.ml.types.model_manifest import ModelManifest
from pirn.domains.ml.types.trained_model_payload import TrainedModelPayload


def _deserialize(body: bytes, algorithm: str) -> TrainedModelPayload:
    try:
        raw = joblib.load(io.BytesIO(body))
    except Exception:
        raw = pickle.loads(body)
    estimator = FittedEstimator(estimator=raw, algorithm=algorithm)
    model_id = f"{algorithm}_{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}"
    manifest = ModelManifest(
        model_id=model_id,
        algorithm=algorithm,
        feature_names=(),
        target_name="",
        created_at=datetime.now(UTC),
    )
    return TrainedModelPayload(metadata=manifest, data=estimator)


class TrainedModelObjectStoreAssembler(Assembler):
    """Assemble a :class:`TrainedModelPayload` from raw serialised model bytes.

    Receives bytes from an upstream connector knot (e.g. an object-store read
    source) and deserialises them into a typed :class:`TrainedModelPayload`.
    Performs no I/O.
    """

    def __init__(
        self,
        *,
        body: Knot,
        algorithm: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(body=body, algorithm=algorithm, _config=_config, **kwargs)

    async def process(
        self,
        body: bytes,
        algorithm: str,
        **_: Any,
    ) -> TrainedModelPayload:
        """Deserialise raw model bytes into a :class:`TrainedModelPayload`.

        Args:
            body: Raw serialised model bytes from an object store or other connector.
            algorithm: Non-empty string naming the algorithm (e.g. ``"RandomForestClassifier"``).

        Returns:
            :class:`TrainedModelPayload` with a :class:`FittedEstimator` and a
            :class:`ModelManifest` populated from the loaded estimator.

        Raises:
            TypeError: If ``body`` is not ``bytes`` or ``algorithm`` is not a ``str``.
            ValueError: If ``algorithm`` is empty or ``body`` is empty.
        """
        if not isinstance(body, bytes):
            raise TypeError(
                f"TrainedModelObjectStoreAssembler: body must be bytes, got {type(body).__name__}"
            )
        if not isinstance(algorithm, str):
            raise TypeError(
                f"TrainedModelObjectStoreAssembler: algorithm must be str, got {type(algorithm).__name__}"
            )
        if not body:
            raise ValueError("TrainedModelObjectStoreAssembler: body must be non-empty")
        if not algorithm:
            raise ValueError("TrainedModelObjectStoreAssembler: algorithm must be non-empty")
        return await asyncio.to_thread(_deserialize, body, algorithm)

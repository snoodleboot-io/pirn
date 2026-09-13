"""Unit tests for :class:`TrainedModelObjectStoreAssembler`."""

from __future__ import annotations

import io
import unittest

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_ml.assemblers.trained_model_object_store_assembler import (
    TrainedModelObjectStoreAssembler,
)
from pirn_ml.types.trained_model_payload import TrainedModelPayload

joblib = pytest.importorskip("joblib")


def _body_param() -> Parameter:
    return Parameter("body", bytes, _config=KnotConfig(id="body"))


def _make() -> TrainedModelObjectStoreAssembler:
    return TrainedModelObjectStoreAssembler(
        body=_body_param(),
        algorithm="LogisticRegression",
        _config=KnotConfig(id="assembler"),
    )


def _joblib_bytes(obj: object) -> bytes:
    buf = io.BytesIO()
    joblib.dump(obj, buf)
    return buf.getvalue()


class TestTrainedModelObjectStoreAssembler(unittest.IsolatedAsyncioTestCase):
    async def test_returns_trained_model_payload(self) -> None:
        knot = _make()
        body = _joblib_bytes({"coef": [1.0, 2.0]})
        result = await knot.process(body=body, algorithm="LogisticRegression")
        assert isinstance(result, TrainedModelPayload)

    async def test_estimator_round_trips(self) -> None:
        knot = _make()
        body = _joblib_bytes({"coef": [1.0, 2.0]})
        result = await knot.process(body=body, algorithm="LogisticRegression")
        assert result.estimator.estimator == {"coef": [1.0, 2.0]}

    async def test_manifest_algorithm_matches(self) -> None:
        knot = _make()
        body = _joblib_bytes({"coef": [1.0]})
        result = await knot.process(body=body, algorithm="LogisticRegression")
        assert result.manifest.algorithm == "LogisticRegression"

    async def test_falls_back_to_pickle_on_joblib_failure(self) -> None:
        import pickle

        knot = _make()
        body = pickle.dumps({"coef": [3.0]})
        result = await knot.process(body=body, algorithm="RandomForest")
        assert result.estimator.estimator == {"coef": [3.0]}

    async def test_rejects_non_bytes_body(self) -> None:
        knot = _make()
        with pytest.raises(TypeError, match="body must be bytes"):
            await knot.process(body="not-bytes", algorithm="rf")  # type: ignore[arg-type]

    async def test_rejects_non_str_algorithm(self) -> None:
        knot = _make()
        with pytest.raises(TypeError, match="algorithm must be str"):
            await knot.process(body=b"x", algorithm=123)  # type: ignore[arg-type]

    async def test_rejects_empty_body(self) -> None:
        knot = _make()
        with pytest.raises(ValueError, match="body must be non-empty"):
            await knot.process(body=b"", algorithm="rf")

    async def test_rejects_empty_algorithm(self) -> None:
        knot = _make()
        with pytest.raises(ValueError, match="algorithm must be non-empty"):
            await knot.process(body=_joblib_bytes({"a": 1}), algorithm="")

"""Unit tests for :class:`EntropyEstimator`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.nonlinear.entropy_estimator import EntropyEstimator
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_invalid_entropy_kind(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="entropy_kind"):
                EntropyEstimator(
                    signal=sig,
                    entropy_kind="bogus",
                    embedding_dim=2,
                    _config=KnotConfig(id="e"),
                )

    def test_rejects_non_positive_embedding_dim(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="embedding_dim"):
                EntropyEstimator(
                    signal=sig,
                    entropy_kind="sample",
                    embedding_dim=0,
                    _config=KnotConfig(id="e"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_estimator_dict(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            EntropyEstimator(
                signal=sig,
                entropy_kind="sample",
                embedding_dim=2,
                _config=KnotConfig(id="e"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["e"]
        assert out["entropy_kind"] == "sample"
        assert out["embedding_dim"] == 2

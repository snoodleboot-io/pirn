"""Unit tests for :class:`ARModelEstimator`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.statistical.ar_model_estimator import ARModelEstimator
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction:
    def test_rejects_non_positive_order(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="positive integer"):
                ARModelEstimator(
                    signal=sig, order=0, method="burg", _config=KnotConfig(id="ar")
                )

    def test_rejects_invalid_method(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with pytest.raises(ValueError, match="method"):
                ARModelEstimator(
                    signal=sig,
                    order=4,
                    method="least_squares",
                    _config=KnotConfig(id="ar"),
                )

    def test_accepts_all_valid_methods(self) -> None:
        for method in ("burg", "yule_walker", "ols"):
            with Tapestry():
                sig = emit_signal_frame(_config=KnotConfig(id="sig"))
                ARModelEstimator(
                    signal=sig, order=4, method=method, _config=KnotConfig(id="ar")
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_emits_dict_with_correct_keys(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            ARModelEstimator(
                signal=sig, order=3, method="burg", _config=KnotConfig(id="ar")
            )
        result = await t.run(RunRequest())
        out = result.outputs["ar"]
        assert isinstance(out, dict)
        assert set(out.keys()) == {"coefficients", "order", "method", "variance"}
        assert out["order"] == 3
        assert out["method"] == "burg"
        assert len(out["coefficients"]) == 3
        assert isinstance(out["variance"], float)

"""Unit tests for :class:`VshaleCalculator`."""

from __future__ import annotations

import unittest
from typing import Any

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.well.vshale_calculator import VshaleCalculator
from pirn.tapestry import Tapestry


class _GRSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> list[dict[str, Any]]:
        return [
            {"depth_ft": 1000.0, "gr_api": 20.0},   # clean sand
            {"depth_ft": 1001.0, "gr_api": 120.0},  # shale
            {"depth_ft": 1002.0, "gr_api": 70.0},   # intermediate
        ]


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_gr_shale_lte_gr_clean(self) -> None:
        k = VshaleCalculator.__new__(VshaleCalculator)
        object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaisesRegex(ValueError, "gr_shale"):
            await k.process(
                gr_log=[],
                gr_clean=100.0,
                gr_shale=50.0,
                method="linear",
            )

    async def test_rejects_invalid_method(self) -> None:
        k = VshaleCalculator.__new__(VshaleCalculator)
        object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaisesRegex(ValueError, "method"):
            await k.process(
                gr_log=[],
                gr_clean=20.0,
                gr_shale=120.0,
                method="steiber",
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_linear_vshale(self) -> None:
        with Tapestry() as t:
            src = _GRSource(_config=KnotConfig(id="src"))
            VshaleCalculator(
                gr_log=src,
                gr_clean=20.0,
                gr_shale=120.0,
                method="linear",
                _config=KnotConfig(id="vsh"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["vsh"]
        assert len(out) == 3
        assert out[0]["vshale"] == pytest.approx(0.0)
        assert out[1]["vshale"] == pytest.approx(1.0)
        assert 0.0 < out[2]["vshale"] < 1.0

    async def test_nonlinear_methods_return_valid_vshale(self) -> None:
        for method in ["larionov_older", "larionov_tertiary", "clavier"]:
            with self.subTest(method=method):
                with Tapestry() as t:
                    src = _GRSource(_config=KnotConfig(id="src"))
                    VshaleCalculator(
                        gr_log=src,
                        gr_clean=20.0,
                        gr_shale=120.0,
                        method=method,
                        _config=KnotConfig(id="vsh"),
                    )
                result = await t.run(RunRequest())
                out = result.outputs["vsh"]
                for entry in out:
                    assert 0.0 <= entry["vshale"] <= 1.0

"""Unit tests for :class:`CoreToLogDepthMatcher`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.well.core_to_log_depth_matcher import CoreToLogDepthMatcher
from pirn.tapestry import Tapestry


class _CoreSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> list[dict[str, Any]]:
        return [{"depth_ft": 1000.0, "value": 0.15}, {"depth_ft": 1005.0, "value": 0.18}]


class _LogSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> list[dict[str, Any]]:
        return [{"depth_ft": 1001.5, "value": 0.14}, {"depth_ft": 1006.0, "value": 0.17}]


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_max_shift(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_shift_ft"):
            with Tapestry():
                c = _CoreSource(_config=KnotConfig(id="c"))
                l = _LogSource(_config=KnotConfig(id="l"))
                CoreToLogDepthMatcher(
                    core_data=c, log_data=l, max_shift_ft=0.0, _config=KnotConfig(id="cdm")
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_matches_depths(self) -> None:
        with Tapestry() as t:
            c = _CoreSource(_config=KnotConfig(id="c"))
            l = _LogSource(_config=KnotConfig(id="l"))
            CoreToLogDepthMatcher(
                core_data=c, log_data=l, max_shift_ft=5.0, _config=KnotConfig(id="cdm")
            )
        result = await t.run(RunRequest())
        out = result.outputs["cdm"]
        assert isinstance(out, list)
        assert len(out) == 2
        assert "core_depth_ft" in out[0]
        assert "matched_log_depth_ft" in out[0]
        assert "shift_ft" in out[0]

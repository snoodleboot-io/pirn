"""Unit tests for :class:`EnvironmentalCorrectionApplicator`."""

from __future__ import annotations

from typing import Any
import unittest

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.well.environmental_correction_applicator import (
    EnvironmentalCorrectionApplicator,
)
from pirn.tapestry import Tapestry


class _LogSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> list[dict[str, Any]]:
        return [{"depth_ft": 1000.0, "raw_value": 50.0}]


class TestConstruction(unittest.TestCase):
    def test_rejects_invalid_log_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "log_type"):
            with Tapestry():
                src = _LogSource(_config=KnotConfig(id="src"))
                EnvironmentalCorrectionApplicator(
                    log_curve=src,
                    correction_table={"correction_factor": 1.05},
                    log_type="caliper",
                    _config=KnotConfig(id="eca"),
                )

    def test_rejects_non_dict_correction_table(self) -> None:
        with self.assertRaisesRegex(TypeError, "correction_table"):
            with Tapestry():
                src = _LogSource(_config=KnotConfig(id="src"))
                EnvironmentalCorrectionApplicator(
                    log_curve=src,
                    correction_table="not_a_dict",  # type: ignore[arg-type]
                    log_type="density",
                    _config=KnotConfig(id="eca"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_applies_correction(self) -> None:
        with Tapestry() as t:
            src = _LogSource(_config=KnotConfig(id="src"))
            EnvironmentalCorrectionApplicator(
                log_curve=src,
                correction_table={"correction_factor": 1.1},
                log_type="density",
                _config=KnotConfig(id="eca"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["eca"]
        assert len(out) == 1
        assert out[0]["corrected_value"] == pytest.approx(55.0)
        assert out[0]["raw_value"] == 50.0

"""Unit tests for :class:`EnvironmentalCorrectionApplicator`."""

from __future__ import annotations

from typing import Any
import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.well.environmental_correction_applicator import (
    EnvironmentalCorrectionApplicator,
)

_LOG_CURVE: list[dict[str, Any]] = [{"depth_ft": 1000.0, "raw_value": 50.0}]


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> EnvironmentalCorrectionApplicator:
        return EnvironmentalCorrectionApplicator(
            log_curve=None,  # type: ignore[arg-type]
            correction_table={"correction_factor": 1.1},
            log_type="density",
            _config=KnotConfig(id="eca", validate_io=False),
        )

    async def test_rejects_invalid_log_type(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "log_type"):
            await knot.process(
                log_curve=_LOG_CURVE,
                correction_table={"correction_factor": 1.05},
                log_type="caliper",
            )

    async def test_rejects_non_dict_correction_table(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "correction_table"):
            await knot.process(
                log_curve=_LOG_CURVE,
                correction_table="not_a_dict",  # type: ignore[arg-type]
                log_type="density",
            )

    async def test_applies_correction(self) -> None:
        knot = self._make_knot()
        out = await knot.process(
            log_curve=_LOG_CURVE,
            correction_table={"correction_factor": 1.1},
            log_type="density",
        )
        assert len(out) == 1
        assert out[0]["corrected_value"] == pytest.approx(55.0)
        assert out[0]["raw_value"] == 50.0

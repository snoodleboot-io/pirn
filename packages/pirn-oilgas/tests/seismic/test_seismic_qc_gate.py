"""Unit tests for the deprecated :class:`SeismicQCGate` alias."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig

from pirn_oilgas.seismic.seismic_qc_check import SeismicQCCheck
from pirn_oilgas.seismic.seismic_qc_gate import SeismicQCGate

_PASSING: dict[str, Any] = {"traces": [{"samples": [1.0]}] * 10, "fold": 20}


class TestSeismicQCGateAlias(unittest.IsolatedAsyncioTestCase):
    def test_warns_deprecation_on_construction(self) -> None:
        with self.assertWarns(DeprecationWarning):
            knot = SeismicQCGate(
                data=None,  # type: ignore[arg-type]
                max_null_pct=10.0,
                min_fold=10,
                max_amplitude=10000.0,
                _config=KnotConfig(id="qc", validate_io=False),
            )
        assert isinstance(knot, SeismicQCCheck)

    async def test_process_behaves_like_seismic_qc_check(self) -> None:
        with self.assertWarns(DeprecationWarning):
            knot = SeismicQCGate(
                data=None,  # type: ignore[arg-type]
                max_null_pct=10.0,
                min_fold=10,
                max_amplitude=10000.0,
                _config=KnotConfig(id="qc", validate_io=False),
            )
        out = await knot.process(
            data=_PASSING,
            max_null_pct=10.0,
            min_fold=10,
            max_amplitude=10000.0,
        )
        assert out["passed"] is True

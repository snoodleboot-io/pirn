"""Unit tests for :class:`SeismicQCGate`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.seismic.seismic_qc_gate import SeismicQCGate
from pirn.tapestry import Tapestry


class _PassingDataSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        return {"traces": [{"samples": [1.0]}] * 10, "fold": 20}


class _LowFoldSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        return {"traces": [], "fold": 5}


class TestConstruction(unittest.TestCase):
    def test_rejects_out_of_range_null_pct(self) -> None:
        with self.assertRaisesRegex(ValueError, "max_null_pct"):
            with Tapestry():
                src = _PassingDataSource(_config=KnotConfig(id="src"))
                SeismicQCGate(
                    data=src,
                    max_null_pct=110.0,
                    min_fold=10,
                    max_amplitude=10000.0,
                    _config=KnotConfig(id="qc"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_passes_valid_data(self) -> None:
        with Tapestry() as t:
            src = _PassingDataSource(_config=KnotConfig(id="src"))
            SeismicQCGate(
                data=src,
                max_null_pct=10.0,
                min_fold=10,
                max_amplitude=10000.0,
                _config=KnotConfig(id="qc"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["qc"]
        assert out["passed"] is True
        assert out["trace_count"] == 10

    async def test_records_error_on_low_fold(self) -> None:
        with Tapestry() as t:
            src = _LowFoldSource(_config=KnotConfig(id="src"))
            SeismicQCGate(
                data=src,
                max_null_pct=10.0,
                min_fold=10,
                max_amplitude=10000.0,
                _config=KnotConfig(id="qc"),
            )
        result = await t.run(RunRequest())
        assert any(e.exc_type == "ValueError" for e in result.exceptions)

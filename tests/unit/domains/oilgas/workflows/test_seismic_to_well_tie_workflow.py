"""Unit tests for :class:`SeismicToWellTieWorkflow`."""

from __future__ import annotations

import unittest

try:
    import lasio  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("lasio not installed") from _e

from unittest.mock import patch

import numpy as np

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.types.las_file import LASFile
from pirn.domains.oilgas.types.las_payload import LASPayload
from pirn.domains.oilgas.types.segy_volume import SegyVolume
from pirn.domains.oilgas.workflows.seismic_to_well_tie_workflow import (
    SeismicToWellTieWorkflow,
)
from pirn.tapestry import Tapestry


def _fake_las_decode(body: bytes, well_id: str, curves: tuple, depth_unit: str) -> LASPayload:
    return LASPayload(
        metadata=LASFile(well_id=well_id, curves=curves, depth_unit=depth_unit),
        data={c: np.zeros(100, dtype=np.float64) for c in curves},
    )


def _fake_segy_decode(body: bytes, volume_id: str) -> SegyVolume:
    return SegyVolume(volume_id=volume_id, inline_count=10, xline_count=20, sample_count=500)


class TestProcess(unittest.IsolatedAsyncioTestCase):

    def _make_knot(self) -> SeismicToWellTieWorkflow:
        return SeismicToWellTieWorkflow(
            segy_body=Parameter("segy_body", bytes, default=b"segy-bytes"),
            volume_id="vol",
            las_body=Parameter("las_body", bytes, default=b"las-bytes"),
            well_id="W",
            las_curves=("GR",),
            cmp_inline=10,
            cmp_xline=20,
            initial_velocity_m_s=2200.0,
            _config=KnotConfig(id="wf"),
        )

    async def test_rejects_non_bytes_segy_body(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "segy_body must be bytes"):
            await knot.process(
                segy_body="not-bytes",  # type: ignore[arg-type]
                volume_id="vol",
                las_body=b"las-bytes",
                well_id="W",
                las_curves=("GR",),
                cmp_inline=10,
                cmp_xline=20,
                initial_velocity_m_s=2200.0,
            )

    async def test_rejects_empty_las_curves(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "las_curves"):
            await knot.process(
                segy_body=b"segy-bytes",
                volume_id="vol",
                las_body=b"las-bytes",
                well_id="W",
                las_curves=(),
                cmp_inline=10,
                cmp_xline=20,
                initial_velocity_m_s=2200.0,
            )

    async def test_inner_pipeline_runs(self) -> None:
        with Tapestry() as t:
            self._make_knot()
        with patch(
            "pirn.domains.oilgas.assemblers.las_object_store_assembler._decode",
            side_effect=_fake_las_decode,
        ), patch(
            "pirn.domains.oilgas.assemblers.segy_object_store_assembler._decode",
            side_effect=_fake_segy_decode,
        ):
            result = await t.run(RunRequest())
        assert result.succeeded
        assert "wf" in result.outputs

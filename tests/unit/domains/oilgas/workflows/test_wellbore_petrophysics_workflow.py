"""Unit tests for :class:`WellborePetrophysicsWorkflow`."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import numpy as np

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.assemblers.las_object_store_assembler import LasObjectStoreAssembler
from pirn.domains.oilgas.types.las_file import LASFile
from pirn.domains.oilgas.types.las_payload import LASPayload
from pirn.domains.oilgas.workflows.wellbore_petrophysics_workflow import (
    WellborePetrophysicsWorkflow,
)
from pirn.tapestry import Tapestry


def _fake_decode(body: bytes, well_id: str, curves: tuple, depth_unit: str) -> LASPayload:
    return LASPayload(
        metadata=LASFile(well_id=well_id, curves=curves, depth_unit=depth_unit),
        data={c: np.zeros(100, dtype=np.float64) for c in curves},
    )


class TestProcess(unittest.IsolatedAsyncioTestCase):

    def _body_param(self) -> Parameter:
        return Parameter("body", bytes, default=b"las-bytes")

    def _make_knot(self) -> WellborePetrophysicsWorkflow:
        return WellborePetrophysicsWorkflow(
            body=self._body_param(),
            well_id="W",
            curves=("GR", "RHOB", "NPHI", "RT"),
            required_curves=("GR",),
            target_depth_step=0.5,
            rw=0.05,
            _config=KnotConfig(id="wf"),
        )

    async def test_rejects_non_bytes_body(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "body must be bytes"):
            await knot.process(
                body="not-bytes",  # type: ignore[arg-type]
                well_id="W",
                curves=("GR", "RHOB", "NPHI", "RT"),
                required_curves=("GR",),
                target_depth_step=0.5,
                rw=0.05,
            )

    async def test_rejects_empty_curves(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "curves"):
            await knot.process(
                body=b"las-bytes",
                well_id="W",
                curves=(),
                required_curves=("GR",),
                target_depth_step=0.5,
                rw=0.05,
            )

    async def test_rejects_empty_required_curves(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "required_curves"):
            await knot.process(
                body=b"las-bytes",
                well_id="W",
                curves=("GR",),
                required_curves=(),
                target_depth_step=0.5,
                rw=0.05,
            )

    async def test_inner_pipeline_completes(self) -> None:
        with Tapestry() as t:
            self._make_knot()
        with patch(
            "pirn.domains.oilgas.assemblers.las_object_store_assembler._decode",
            side_effect=_fake_decode,
        ):
            result = await t.run(RunRequest())
        assert result.succeeded
        assert "wf" in result.outputs

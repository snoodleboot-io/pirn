"""Unit tests for :class:`PetrophysicalEvaluator`."""

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
from pirn.domains.oilgas.well.petrophysical_evaluator import PetrophysicalEvaluator
from pirn.tapestry import Tapestry


def _fake_decode(body: bytes, well_id: str, curves: tuple, depth_unit: str) -> LASPayload:
    return LASPayload(
        metadata=LASFile(well_id=well_id, curves=curves, depth_unit=depth_unit),
        data={c: np.zeros(100, dtype=np.float64) for c in curves},
    )


class TestConstruction(unittest.TestCase):
    def test_requires_payload_kwarg(self) -> None:
        with self.assertRaisesRegex(TypeError, "payload"):
            PetrophysicalEvaluator(_config=KnotConfig(id="pe"))  # type: ignore[call-arg]


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_appends_interpreted_curves(self) -> None:
        with Tapestry() as t:
            body = Parameter("body", bytes, _config=KnotConfig(id="body"))
            las = LasObjectStoreAssembler(
                body=body,
                well_id="W",
                curves=("GR", "RHOB"),
                depth_unit="m",
                _config=KnotConfig(id="i"),
            )
            PetrophysicalEvaluator(
                payload=las,
                _config=KnotConfig(id="pe"),
            )
        with patch(
            "pirn.domains.oilgas.assemblers.las_object_store_assembler._decode",
            side_effect=_fake_decode,
        ):
            result = await t.run(RunRequest(parameters={"body": b"las-bytes"}))
        out = result.outputs["pe"]
        assert isinstance(out, LASPayload)
        assert "VSH" in out.curve_data
        assert "PHIE" in out.curve_data
        assert "SW" in out.curve_data

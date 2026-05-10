"""Unit tests for :class:`PetrophysicalEvaluator`."""

from __future__ import annotations

import unittest

import numpy as np

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.types.las_file import LASFile
from pirn.domains.oilgas.types.las_payload import LASPayload
from pirn.domains.oilgas.well.las_file_ingester import LasFileIngester
from pirn.domains.oilgas.well.petrophysical_evaluator import PetrophysicalEvaluator
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_requires_payload_kwarg(self) -> None:
        with self.assertRaisesRegex(TypeError, "payload"):
            PetrophysicalEvaluator(_config=KnotConfig(id="pe"))  # type: ignore[call-arg]


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_appends_interpreted_curves(self) -> None:
        with Tapestry() as t:
            las = LasFileIngester(
                file_path="/x",
                well_id="W",
                curves=("GR", "RHOB"),
                _config=KnotConfig(id="i"),
            )
            PetrophysicalEvaluator(
                payload=las,
                _config=KnotConfig(id="pe"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["pe"]
        assert isinstance(out, LASPayload)
        assert "VSH" in out.curve_data
        assert "PHIE" in out.curve_data
        assert "SW" in out.curve_data

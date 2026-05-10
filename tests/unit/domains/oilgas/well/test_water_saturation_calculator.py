"""Unit tests for :class:`WaterSaturationCalculator`."""

from __future__ import annotations

import unittest

import numpy as np

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.types.las_file import LASFile
from pirn.domains.oilgas.types.las_payload import LASPayload
from pirn.domains.oilgas.well.las_file_ingester import LasFileIngester
from pirn.domains.oilgas.well.water_saturation_calculator import WaterSaturationCalculator
from pirn.tapestry import Tapestry

_LAS = LASPayload(
    metadata=LASFile(well_id="W", curves=("GR",)),
    data={"GR": np.zeros(10)},
)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_method(self) -> None:
        k = WaterSaturationCalculator.__new__(WaterSaturationCalculator)
        object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaisesRegex(ValueError, "method"):
            await k.process(
                payload=_LAS,
                method="bogus",
                rw=0.05,
            )

    async def test_rejects_non_positive_rw(self) -> None:
        k = WaterSaturationCalculator.__new__(WaterSaturationCalculator)
        object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaisesRegex(ValueError, "rw"):
            await k.process(
                payload=_LAS,
                method="archie",
                rw=0.0,
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_appends_sw_curve(self) -> None:
        with Tapestry() as t:
            las = LasFileIngester(
                file_path="/x",
                well_id="W",
                curves=("GR", "RHOB", "NPHI", "RT"),
                _config=KnotConfig(id="i"),
            )
            WaterSaturationCalculator(
                payload=las,
                method="archie",
                rw=0.05,
                _config=KnotConfig(id="sw"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["sw"]
        assert isinstance(out, LASPayload)
        assert "SW_archie" in out.curve_data

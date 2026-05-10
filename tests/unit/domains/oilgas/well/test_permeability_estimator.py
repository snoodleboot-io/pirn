"""Unit tests for :class:`PermeabilityEstimator`."""

from __future__ import annotations

import unittest

import numpy as np

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.types.las_file import LASFile
from pirn.domains.oilgas.types.las_payload import LASPayload
from pirn.domains.oilgas.well.las_file_ingester import LasFileIngester
from pirn.domains.oilgas.well.permeability_estimator import PermeabilityEstimator
from pirn.tapestry import Tapestry

_LAS = LASPayload(
    metadata=LASFile(well_id="W", curves=("GR",)),
    data={"GR": np.zeros(10)},
)


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_method(self) -> None:
        k = PermeabilityEstimator.__new__(PermeabilityEstimator)
        object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaisesRegex(ValueError, "method"):
            await k.process(
                payload=_LAS,
                method="bogus",
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_appends_permeability_curve(self) -> None:
        with Tapestry() as t:
            las = LasFileIngester(
                file_path="/x",
                well_id="W",
                curves=("GR", "PHI_density"),
                _config=KnotConfig(id="i"),
            )
            PermeabilityEstimator(
                payload=las,
                method="timur",
                _config=KnotConfig(id="p"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["p"]
        assert isinstance(out, LASPayload)
        assert "K_timur" in out.curve_data

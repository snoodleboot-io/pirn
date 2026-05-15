"""Unit tests for :class:`PermeabilityEstimator`."""

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
from pirn.domains.oilgas.well.permeability_estimator import PermeabilityEstimator
from pirn.tapestry import Tapestry

_LAS = LASPayload(
    metadata=LASFile(well_id="W", curves=("GR",)),
    data={"GR": np.zeros(10)},
)


def _fake_decode(body: bytes, well_id: str, curves: tuple, depth_unit: str) -> LASPayload:
    return LASPayload(
        metadata=LASFile(well_id=well_id, curves=curves, depth_unit=depth_unit),
        data={c: np.zeros(100, dtype=np.float64) for c in curves},
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
            body = Parameter("body", bytes, _config=KnotConfig(id="body"))
            las = LasObjectStoreAssembler(
                body=body,
                well_id="W",
                curves=("GR", "PHI_density"),
                depth_unit="m",
                _config=KnotConfig(id="i"),
            )
            PermeabilityEstimator(
                payload=las,
                method="timur",
                _config=KnotConfig(id="p"),
            )
        with patch(
            "pirn.domains.oilgas.assemblers.las_object_store_assembler._decode",
            side_effect=_fake_decode,
        ):
            result = await t.run(RunRequest(parameters={"body": b"las-bytes"}))
        out = result.outputs["p"]
        assert isinstance(out, LASPayload)
        assert "K_timur" in out.curve_data

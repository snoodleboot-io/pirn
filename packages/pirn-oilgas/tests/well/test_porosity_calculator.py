"""Unit tests for :class:`PorosityCalculator`."""

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
from pirn.tapestry import Tapestry
from pirn_oilgas.assemblers.las_object_store_assembler import LasObjectStoreAssembler
from pirn_oilgas.types.las_file import LASFile
from pirn_oilgas.types.las_payload import LASPayload
from pirn_oilgas.well.porosity_calculator import PorosityCalculator

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
        k = PorosityCalculator.__new__(PorosityCalculator)
        object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaisesRegex(ValueError, "method"):
            await k.process(
                payload=_LAS,
                method="not_real",
                matrix_density=2.65,
                fluid_density=1.0,
            )

    async def test_rejects_non_positive_density(self) -> None:
        k = PorosityCalculator.__new__(PorosityCalculator)
        object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaisesRegex(ValueError, "matrix_density"):
            await k.process(
                payload=_LAS,
                method="density",
                matrix_density=-2.65,
                fluid_density=1.0,
            )

    async def test_rejects_inverted_densities(self) -> None:
        k = PorosityCalculator.__new__(PorosityCalculator)
        object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaisesRegex(ValueError, "fluid_density"):
            await k.process(
                payload=_LAS,
                method="density",
                matrix_density=1.0,
                fluid_density=2.65,
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_appends_porosity_curve(self) -> None:
        with Tapestry() as t:
            body = Parameter("body", bytes, _config=KnotConfig(id="body"))
            las = LasObjectStoreAssembler(
                body=body,
                well_id="W",
                curves=("GR", "RHOB"),
                depth_unit="m",
                _config=KnotConfig(id="i"),
            )
            PorosityCalculator(
                payload=las,
                method="density",
                matrix_density=2.65,
                fluid_density=1.0,
                _config=KnotConfig(id="p"),
            )
        with patch(
            "pirn_oilgas.assemblers.las_object_store_assembler._decode",
            side_effect=_fake_decode,
        ):
            result = await t.run(RunRequest(parameters={"body": b"las-bytes"}))
        out = result.outputs["p"]
        assert isinstance(out, LASPayload)
        assert "PHI_density" in out.curve_data

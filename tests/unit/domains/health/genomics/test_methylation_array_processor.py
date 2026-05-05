"""Unit tests for :class:`MethylationArrayProcessor`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.domains.health.genomics.methylation_array_processor import MethylationArrayProcessor
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_invalid_array_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "array_type"):
            MethylationArrayProcessor(
                idat_data=Parameter("id", dict, default={}, _config=KnotConfig(id="id")),
                array_type="850k",
                normalization="ssnoob",
                _config=KnotConfig(id="m"),
            )

    def test_rejects_invalid_normalization(self) -> None:
        with self.assertRaisesRegex(ValueError, "normalization"):
            MethylationArrayProcessor(
                idat_data=Parameter("id", dict, default={}, _config=KnotConfig(id="id")),
                array_type="epic",
                normalization="combat",
                _config=KnotConfig(id="m"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_dict(self) -> None:
        idat = {"red_channel": [0.5], "green_channel": [0.4], "sample_id": "S1"}
        with Tapestry() as t:
            MethylationArrayProcessor(
                idat_data=Parameter("id", dict, default=idat, _config=KnotConfig(id="id")),
                array_type="epic",
                normalization="ssnoob",
                _config=KnotConfig(id="m"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["m"]
        assert isinstance(out, dict)
        assert "sample_id" in out
        assert "beta_values" in out
        assert "m_values" in out
        assert "detection_p_values" in out

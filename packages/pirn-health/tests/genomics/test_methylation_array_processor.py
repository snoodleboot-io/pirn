"""Unit tests for :class:`MethylationArrayProcessor`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.tapestry import Tapestry
from pirn_health.genomics.methylation_array_processor import MethylationArrayProcessor

_CFG = KnotConfig(id="m")
_IDAT = {"red_channel": [0.5], "green_channel": [0.4], "sample_id": "S1"}


def _make_knot() -> MethylationArrayProcessor:
    with Tapestry():
        src = Parameter("id", dict, default=_IDAT, _config=KnotConfig(id="id"))
        return MethylationArrayProcessor(
            idat_data=src,
            array_type="epic",
            normalization="ssnoob",
            _config=_CFG,
        )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_array_type(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "array_type"):
            await knot.process(idat_data=_IDAT, array_type="850k", normalization="ssnoob")

    async def test_rejects_invalid_normalization(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(ValueError, "normalization"):
            await knot.process(idat_data=_IDAT, array_type="epic", normalization="combat")

    async def test_rejects_non_dict_idat(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(TypeError, "idat_data"):
            await knot.process(idat_data="not_a_dict", array_type="epic", normalization="ssnoob")  # type: ignore[arg-type]

    async def test_returns_dict(self) -> None:
        knot = _make_knot()
        out = await knot.process(idat_data=_IDAT, array_type="epic", normalization="ssnoob")
        assert isinstance(out, dict)
        assert "sample_id" in out
        assert "beta_values" in out
        assert "m_values" in out
        assert "detection_p_values" in out

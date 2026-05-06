"""Unit tests for :class:`PathologyFeatureExtractor`."""

from __future__ import annotations

from collections.abc import Mapping
import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.health.pathology.pathology_feature_extractor import PathologyFeatureExtractor
from pirn.tapestry import Tapestry

_CFG = KnotConfig(id="f")
_CELL_COUNTS: dict[tuple[int, int], int] = {(0, 0): 10, (0, 512): 4}
_MITOSIS_INT = 6


def _make_knot() -> PathologyFeatureExtractor:
    with Tapestry():
        cells = Parameter("cells", dict, default=_CELL_COUNTS, _config=KnotConfig(id="cells"))
        mitosis = Parameter("mitosis", int, default=_MITOSIS_INT, _config=KnotConfig(id="mitosis"))
        return PathologyFeatureExtractor(cell_counts=cells, mitosis_counts=mitosis, _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_mitosis_type(self) -> None:
        knot = _make_knot()
        with self.assertRaisesRegex(TypeError, "Mapping or int"):
            await knot.process(cell_counts=_CELL_COUNTS, mitosis_counts="bad")  # type: ignore[arg-type]

    async def test_returns_per_tile_features(self) -> None:
        knot = _make_knot()
        out = await knot.process(cell_counts=_CELL_COUNTS, mitosis_counts=_MITOSIS_INT)
        assert isinstance(out, Mapping)
        assert (0, 0) in out
        assert (0, 512) in out

    async def test_density_calculation(self) -> None:
        knot = _make_knot()
        out = await knot.process(cell_counts=_CELL_COUNTS, mitosis_counts=_MITOSIS_INT)
        # 6 mitosis split across 2 tiles -> 3 each; cell_count=10 -> density 0.3
        assert out[(0, 0)]["cell_count"] == 10
        assert out[(0, 0)]["mitosis_count"] == 3
        assert out[(0, 0)]["mitosis_density"] == pytest.approx(0.3)
        assert out[(0, 512)]["cell_count"] == 4
        assert out[(0, 512)]["mitosis_count"] == 3
        assert out[(0, 512)]["mitosis_density"] == pytest.approx(0.75)

    async def test_accepts_mapping_mitosis(self) -> None:
        knot = _make_knot()
        per_tile = {(0, 0): 2, (0, 512): 1}
        out = await knot.process(cell_counts=_CELL_COUNTS, mitosis_counts=per_tile)
        assert out[(0, 0)]["mitosis_count"] == 2
        assert out[(0, 512)]["mitosis_count"] == 1

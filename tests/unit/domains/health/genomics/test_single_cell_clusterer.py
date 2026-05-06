"""Unit tests for :class:`SingleCellClusterer`."""

from __future__ import annotations

from collections.abc import Mapping
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.health.genomics.single_cell_clusterer import SingleCellClusterer

_CFG = KnotConfig(id="c")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> SingleCellClusterer:
        return SingleCellClusterer(
            count_matrix_path="x",
            cell_ids=["c1", "c2"],
            resolution=0.5,
            _config=_CFG,
        )

    async def test_rejects_empty_count_path(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await knot.process(count_matrix_path="", cell_ids=[], resolution=0.5)

    async def test_rejects_non_sequence_cells(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "cell_ids"):
            await knot.process(count_matrix_path="x", cell_ids=42, resolution=0.5)  # type: ignore[arg-type]

    async def test_rejects_non_string_cell(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "string"):
            await knot.process(count_matrix_path="x", cell_ids=[1], resolution=0.5)  # type: ignore[list-item]

    async def test_rejects_non_numeric_resolution(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "resolution"):
            await knot.process(count_matrix_path="x", cell_ids=[], resolution="x")  # type: ignore[arg-type]

    async def test_rejects_non_positive_resolution(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "positive"):
            await knot.process(count_matrix_path="x", cell_ids=[], resolution=0.0)

    async def test_returns_per_cell_mapping(self) -> None:
        knot = self._make_knot()
        out = await knot.process(count_matrix_path="x", cell_ids=["c1", "c2"], resolution=0.5)
        assert isinstance(out, Mapping)
        assert set(out.keys()) == {"c1", "c2"}

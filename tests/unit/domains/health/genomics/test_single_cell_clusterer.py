"""Unit tests for :class:`SingleCellClusterer`."""

from __future__ import annotations

from collections.abc import Mapping
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.genomics.single_cell_clusterer import (
    SingleCellClusterer,
)
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_count_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty"):
            SingleCellClusterer(
                count_matrix_path="",
                cell_ids=[],
                resolution=0.5,
                _config=KnotConfig(id="c"),
            )

    def test_rejects_non_sequence_cells(self) -> None:
        with self.assertRaisesRegex(TypeError, "cell_ids"):
            SingleCellClusterer(
                count_matrix_path="x",
                cell_ids=42,  # type: ignore[arg-type]
                resolution=0.5,
                _config=KnotConfig(id="c"),
            )

    def test_rejects_non_string_cell(self) -> None:
        with self.assertRaisesRegex(TypeError, "string"):
            SingleCellClusterer(
                count_matrix_path="x",
                cell_ids=[1],  # type: ignore[list-item]
                resolution=0.5,
                _config=KnotConfig(id="c"),
            )

    def test_rejects_non_numeric_resolution(self) -> None:
        with self.assertRaisesRegex(TypeError, "resolution"):
            SingleCellClusterer(
                count_matrix_path="x",
                cell_ids=[],
                resolution="x",  # type: ignore[arg-type]
                _config=KnotConfig(id="c"),
            )

    def test_rejects_non_positive_resolution(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            SingleCellClusterer(
                count_matrix_path="x",
                cell_ids=[],
                resolution=0.0,
                _config=KnotConfig(id="c"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_per_cell_mapping(self) -> None:
        with Tapestry() as t:
            SingleCellClusterer(
                count_matrix_path="x",
                cell_ids=["c1", "c2"],
                resolution=0.5,
                _config=KnotConfig(id="c"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["c"]
        assert isinstance(out, Mapping)
        assert set(out.keys()) == {"c1", "c2"}

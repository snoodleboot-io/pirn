"""``SingleCellClusterer`` — single-cell clustering (Leiden / Louvain).

Production version wraps ``scanpy`` / ``scvi-tools``; this stub
returns an empty mapping ``cell_id -> cluster_id``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class SingleCellClusterer(Knot):
    """Cluster single cells from a count matrix path."""

    def __init__(
        self,
        *,
        count_matrix_path: str,
        cell_ids: Sequence[str],
        resolution: float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(count_matrix_path, str) or not count_matrix_path:
            raise ValueError(
                "SingleCellClusterer: count_matrix_path must be non-empty string"
            )
        if not isinstance(cell_ids, (list, tuple)):
            raise TypeError(
                "SingleCellClusterer: cell_ids must be list/tuple"
            )
        for cell in cell_ids:
            if not isinstance(cell, str):
                raise TypeError(
                    "SingleCellClusterer: every cell id must be a string"
                )
        if not isinstance(resolution, (int, float)):
            raise TypeError(
                "SingleCellClusterer: resolution must be numeric"
            )
        if float(resolution) <= 0.0:
            raise ValueError(
                "SingleCellClusterer: resolution must be positive"
            )
        self._count_matrix_path = count_matrix_path
        self._cell_ids = tuple(cell_ids)
        self._resolution = float(resolution)
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> Mapping[str, int]:
        return {cell: 0 for cell in self._cell_ids}

"""``PathologyFeatureExtractor`` — compose per-tile pathology features.

Production version assembles morphometric, intensity, and texture
descriptors from cell-detection, mitosis-detection, and segmentation
upstream knots. This stub composes the upstream cell-count and
mitosis-count outputs into per-tile feature vectors carrying
``cell_count``, ``mitosis_count``, and a derived ``mitosis_density``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class PathologyFeatureExtractor(Knot):
    """Combine cell- and mitosis-counts into per-tile feature vectors."""

    def __init__(
        self,
        *,
        cell_counts: Knot,
        mitosis_counts: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(cell_counts, Knot):
            raise TypeError(
                "PathologyFeatureExtractor: cell_counts must be a Knot"
            )
        if not isinstance(mitosis_counts, Knot):
            raise TypeError(
                "PathologyFeatureExtractor: mitosis_counts must be a Knot"
            )
        super().__init__(
            cell_counts=cell_counts,
            mitosis_counts=mitosis_counts,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        cell_counts: Mapping[tuple[int, int], int],
        mitosis_counts: Any,
        **_: Any,
    ) -> Mapping[tuple[int, int], Mapping[str, float | int]]:
        """Combine per-tile cell counts and mitosis counts into feature vectors with mitosis_density.

        Args:
            cell_counts: Mapping of (tile_x, tile_y) coordinate to cell count.
            mitosis_counts: Per-tile mapping or total int of mitotic-figure counts.

        Returns:
            Mapping of (tile_x, tile_y) coordinate to a feature dict containing
            ``cell_count``, ``mitosis_count``, and ``mitosis_density``.

        Raises:
            TypeError: If mitosis_counts is neither a Mapping nor an int.
        """
        per_tile_mitosis = self._coerce_per_tile_mitosis(
            mitosis_counts, cell_counts
        )
        features: dict[tuple[int, int], Mapping[str, float | int]] = {}
        for position, count in cell_counts.items():
            cell_count = int(count)
            mitosis_count = int(per_tile_mitosis.get(position, 0))
            density = mitosis_count / max(cell_count, 1)
            features[position] = {
                "cell_count": cell_count,
                "mitosis_count": mitosis_count,
                "mitosis_density": density,
            }
        return features

    @staticmethod
    def _coerce_per_tile_mitosis(
        mitosis_counts: Any,
        cell_counts: Mapping[tuple[int, int], int],
    ) -> Mapping[tuple[int, int], int]:
        """Accept either a per-tile mapping or a single int total.

        Upstream :class:`MitosisCounter` returns an ``int`` total; future
        versions may emit a per-tile mapping. We support both.
        """
        if isinstance(mitosis_counts, Mapping):
            return {tuple(k): int(v) for k, v in mitosis_counts.items()}
        if isinstance(mitosis_counts, int):
            tile_count = max(len(cell_counts), 1)
            base = mitosis_counts // tile_count
            return {position: base for position in cell_counts}
        raise TypeError(
            "PathologyFeatureExtractor: mitosis_counts must be a Mapping or int"
        )

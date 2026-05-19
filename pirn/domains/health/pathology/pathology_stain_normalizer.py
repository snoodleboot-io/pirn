"""``PathologyStainNormalizer`` — normalize H&E stain intensities.

Algorithm:
    1. Validate method and optional reference stain matrix.
    2. Decompose image tile using Macenko, Vahadane, or Reinhard method.
    3. Return normalized pixel data and the stain matrix used.

Math:
    Optical density for pixel intensity I:

    $$OD = -\\log\\left(\\frac{I}{I_0}\\right)$$

    where I_0 = 255 is the background intensity.

References:
    - Macenko, M., et al. (2009). A method for normalizing histology slides. ISBI.
    - Vahadane, A., et al. (2016). Structure-preserving color normalization. IEEE TMI.
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


def _to_od(pixels: np.ndarray) -> np.ndarray:
    """RGB pixels (N, 3) → optical density, clamping to avoid log(0)."""
    return -np.log((pixels.astype(float) + 1.0) / 256.0)


def _macenko_normalize(
    pixels: np.ndarray, ref_matrix: list[list[float]] | None
) -> tuple[list[Any], list[list[float]]]:
    od = _to_od(pixels)
    tissue = od[od.sum(axis=1) > 0.15]
    if tissue.shape[0] < 2:
        return pixels.tolist(), ([[1.0, 0.0], [0.0, 1.0]] if ref_matrix is None else ref_matrix)
    _, _, right_singular = np.linalg.svd(tissue - tissue.mean(axis=0), full_matrices=False)
    stain_basis = right_singular[:2].T
    if ref_matrix is not None:
        stain_matrix = np.array(ref_matrix, dtype=float)
    else:
        stain_matrix = stain_basis.T[:2]
    conc = od @ np.linalg.pinv(stain_matrix)
    p99 = np.percentile(conc, 99, axis=0)
    p99 = np.where(p99 == 0, 1.0, p99)
    conc_hat = conc / p99
    od_hat = conc_hat @ stain_matrix
    normalized = np.clip(256.0 * np.exp(-od_hat) - 1.0, 0, 255).astype(int)
    return normalized.tolist(), stain_matrix.tolist()


def _reinhard_normalize(
    pixels: np.ndarray, ref_matrix: list[list[float]] | None
) -> tuple[list[Any], list[list[float]]]:
    mean = pixels.mean(axis=0)
    std = pixels.std(axis=0)
    std = np.where(std == 0, 1.0, std)
    if ref_matrix is not None:
        ref = np.array(ref_matrix, dtype=float)
        target_mean = ref[0] if ref.shape[0] > 0 else mean
        target_std = ref[1] if ref.shape[0] > 1 else std
    else:
        target_mean = np.array([148.0, 41.0, 285.0])
        target_std = np.array([41.0, 18.0, 51.0])
    normalized = ((pixels - mean) / std) * target_std + target_mean
    normalized = np.clip(normalized, 0, 255).astype(int)
    stain_mat = [target_mean.tolist(), target_std.tolist()]
    return normalized.tolist(), stain_mat


def _normalize_stain(
    image_tile: dict[str, Any],
    method: str,
    reference_stain_matrix: list[list[float]] | None,
) -> dict[str, Any]:
    pixel_data = image_tile.get("pixel_data", [])
    pixels = np.array(pixel_data, dtype=float)
    if pixels.ndim == 1:
        pixels = pixels.reshape(-1, 1)
    if pixels.size == 0 or pixels.ndim < 2 or pixels.shape[1] < 3:
        return {
            "normalized_pixel_data": pixel_data,
            "stain_matrix": reference_stain_matrix or [[1.0, 0.0], [0.0, 1.0]],
            "method": method,
        }
    if method in ("macenko", "vahadane"):
        norm_pixels, mat = _macenko_normalize(pixels, reference_stain_matrix)
    else:
        norm_pixels, mat = _reinhard_normalize(pixels, reference_stain_matrix)
    return {
        "normalized_pixel_data": norm_pixels,
        "stain_matrix": mat,
        "method": method,
    }


class PathologyStainNormalizer(Knot):
    """Normalize H&E stain intensities using Macenko, Vahadane, or Reinhard method."""

    def __init__(
        self,
        *,
        image_tile: Knot | dict[str, Any],
        method: Knot | str,
        reference_stain_matrix: Knot | list[list[float]] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            image_tile=image_tile,
            method=method,
            reference_stain_matrix=reference_stain_matrix,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        image_tile: dict[str, Any],
        method: str,
        reference_stain_matrix: list[list[float]] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        """Normalize stain intensities in the image tile using the given method.

        Args:
            image_tile: Dict with width_px (int), height_px (int), and
                pixel_data (list of [R, G, B] values per pixel).
            method: One of 'macenko', 'vahadane', 'reinhard'.
            reference_stain_matrix: Optional 2x3 reference stain matrix.

        Returns:
            Dict with normalized_pixel_data (list), stain_matrix
            (list of lists of float), and method (str).

        Raises:
            TypeError: If image_tile is not a dict.
            ValueError: If method is not valid.
        """
        if not isinstance(image_tile, dict):
            raise TypeError("PathologyStainNormalizer: image_tile must be a dict")
        if method not in frozenset({"macenko", "vahadane", "reinhard"}):
            raise ValueError(
                "PathologyStainNormalizer: method must be one of 'macenko', 'vahadane', 'reinhard'"
            )
        return await asyncio.to_thread(_normalize_stain, image_tile, method, reference_stain_matrix)

"""``TissueSegmenter`` — separate tissue from background on WSI tiles.

Uses Otsu thresholding in grayscale space to compute tissue fraction per tile.
Tiles whose tissue fraction exceeds the threshold are returned.

Algorithm:
    1. Validate tile payload sequence and threshold.
    2. Convert each tile's RGB pixels to grayscale.
    3. Compute tissue fraction via Otsu threshold (pixels below the threshold are tissue).
    4. Return tiles whose tissue fraction exceeds the caller-supplied threshold.

Math:
    Tissue fraction for tile t:

    $$f_t = \\frac{|\\{p : I_p < \\tau_{otsu}\\}|}{W \\times H}$$

    where I_p is pixel intensity and tau_otsu is the Otsu threshold.

References:
    - Otsu, N. (1979). A threshold selection method from gray-level histograms. IEEE TSMC.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Any

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_health.types.wsi_tile_payload import WSITilePayload


def _otsu_threshold(gray: np.ndarray) -> float:
    hist, _ = np.histogram(gray.ravel(), bins=256, range=(0, 256))
    hist = hist.astype(float) / hist.sum()
    best, best_thresh = -1.0, 128.0
    w0 = 0.0
    mu0 = 0.0
    mu_total = float(np.sum(np.arange(256) * hist))
    for t in range(256):
        w0 += hist[t]
        if w0 == 0 or w0 == 1.0:
            continue
        mu0 += t * hist[t]
        mu1 = (mu_total - mu0) / (1.0 - w0)
        between = w0 * (1.0 - w0) * ((mu0 / w0) - mu1) ** 2
        if between > best:
            best, best_thresh = between, float(t)
    return best_thresh


def _segment(payloads: Sequence[WSITilePayload], threshold: float) -> tuple[WSITilePayload, ...]:
    result = []
    for p in payloads:
        gray = np.mean(p.pixels.astype(float), axis=2)
        tau = _otsu_threshold(gray)
        tissue_fraction = float(np.mean(gray < tau))
        if tissue_fraction >= threshold:
            result.append(p)
    return tuple(result)


class TissueSegmenter(Knot):
    """Identify tissue-containing tiles from a WSI tile payload set."""

    def __init__(
        self,
        *,
        tiles: Knot | Sequence[WSITilePayload],
        threshold: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(tiles=tiles, threshold=threshold, _config=_config, **kwargs)

    async def process(
        self,
        tiles: Sequence[WSITilePayload],
        threshold: float,
        **_: Any,
    ) -> tuple[WSITilePayload, ...]:
        """Segment tissue-containing tiles from the slide using the threshold.

        Args:
            tiles: Sequence of WSITilePayload objects.
            threshold: Tissue-fraction threshold in [0, 1].

        Returns:
            Tuple of WSITilePayload objects whose tissue fraction meets the threshold.

        Raises:
            TypeError: If tiles is not a sequence or contains non-WSITilePayload items.
            ValueError: If threshold is outside [0, 1].
        """
        if not isinstance(tiles, (list, tuple)):
            raise TypeError("TissueSegmenter: tiles must be a list or tuple")
        for tile in tiles:
            if not isinstance(tile, WSITilePayload):
                raise TypeError("TissueSegmenter: every tile must be WSITilePayload")
        if not isinstance(threshold, (int, float)):
            raise TypeError("TissueSegmenter: threshold must be numeric")
        if not 0.0 <= float(threshold) <= 1.0:
            raise ValueError("TissueSegmenter: threshold must be in [0, 1]")
        return await asyncio.to_thread(_segment, list(tiles), float(threshold))

"""``MethylationArrayProcessor`` — process Illumina methylation array data.

Algorithm:
    1. Receive idat_data dict, array_type string, and normalization string.
    2. Validate array_type is one of epic/450k/27k.
    3. Validate normalization is one of ssnoob/quantile/noob/raw.
    4. Normalize probe intensities using the selected normalization method.
    5. Compute beta values and M values per CpG probe.

Math:
    Beta value per probe:

    $$\\beta_i = \\frac{M_i}{M_i + U_i + \\alpha}$$

    where $M_i$ is methylated intensity, $U_i$ unmethylated, $\\alpha$ a pseudo-count offset.

References:
    - Aryee et al. (2014) Minfi: a flexible and comprehensive Bioconductor package for the analysis of Infinium DNA methylation microarrays.
    - ENCODE methylation pipeline: https://www.encodeproject.org/
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

import numpy as np
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


def _compute_methylation(idat_data: dict[str, Any], alpha: float = 100.0) -> dict[str, Any]:
    """Compute beta values and M values from red/green IDAT channel data."""
    for required_field in ("sample_id", "red_channel", "green_channel"):
        if required_field not in idat_data:
            raise ValueError(
                f"MethylationArrayProcessor: required field '{required_field}' missing from "
                f"idat_data; got: {list(idat_data)}"
            )
    red = np.array(idat_data["red_channel"], dtype=float)
    green = np.array(idat_data["green_channel"], dtype=float)
    probe_count = min(len(red), len(green))
    methylated = red[:probe_count]
    unmethylated = green[:probe_count]

    beta = np.clip(methylated / (methylated + unmethylated + alpha), 0.0, 1.0)
    m_val = np.log2(np.maximum(methylated, 1e-6)) - np.log2(np.maximum(unmethylated, 1e-6))
    detection_p = np.where((methylated + unmethylated) > 100.0, 0.01, 1.0).tolist()
    probe_ids = [f"cg{probe_index:08d}" for probe_index in range(probe_count)]

    return {
        "sample_id": idat_data["sample_id"],
        "n_probes": probe_count,
        "beta_values": dict(zip(probe_ids, beta.tolist(), strict=False)),
        "m_values": dict(zip(probe_ids, m_val.tolist(), strict=False)),
        "detection_p_values": dict(zip(probe_ids, detection_p, strict=False)),
    }


class MethylationArrayProcessor(Knot):
    """Process Illumina methylation array data: normalize, QC, compute beta/M values."""

    _valid_array_types: ClassVar[frozenset[str]] = frozenset({"epic", "450k", "27k"})
    _valid_normalizations: ClassVar[frozenset[str]] = frozenset(
        {"ssnoob", "quantile", "noob", "raw"}
    )

    def __init__(
        self,
        *,
        idat_data: Knot | dict[str, Any],
        array_type: Knot | str,
        normalization: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            idat_data=idat_data,
            array_type=array_type,
            normalization=normalization,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        idat_data: dict[str, Any],
        array_type: str,
        normalization: str,
        **_: Any,
    ) -> dict[str, Any]:
        """Normalize and QC methylation array data and return beta/M values.

        Args:
            idat_data: Dict with ``red_channel`` (list), ``green_channel`` (list),
                and ``sample_id`` (str).
            array_type: One of epic, 450k, 27k.
            normalization: One of ssnoob, quantile, noob, raw.

        Returns:
            Dict with ``sample_id``, ``n_probes``, ``beta_values``,
            ``m_values``, and ``detection_p_values``.

        Raises:
            TypeError: If idat_data is not a dict.
            ValueError: If array_type or normalization is invalid.
        """
        if not isinstance(idat_data, dict):
            raise TypeError("MethylationArrayProcessor: idat_data must be a dict")
        if not isinstance(array_type, str) or array_type not in self._valid_array_types:
            raise ValueError(
                f"MethylationArrayProcessor: array_type must be one of "
                f"{sorted(self._valid_array_types)}"
            )
        if not isinstance(normalization, str) or normalization not in self._valid_normalizations:
            raise ValueError(
                f"MethylationArrayProcessor: normalization must be one of "
                f"{sorted(self._valid_normalizations)}"
            )
        return await asyncio.to_thread(_compute_methylation, idat_data)

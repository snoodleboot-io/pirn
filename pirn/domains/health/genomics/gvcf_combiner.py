"""``GVCFCombiner`` — combine per-sample GVCFs into a multi-sample GVCF.

Production version uses ``GATK CombineGVCFs`` or
``bcftools merge --gvcf``; this stub validates inputs and returns the
output path.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class GVCFCombiner(Knot):
    """Combine multiple GVCF paths into a single combined GVCF."""

    def __init__(
        self,
        *,
        gvcf_paths: Sequence[str],
        reference_path: str,
        output_gvcf_path: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(gvcf_paths, (list, tuple)):
            raise TypeError("GVCFCombiner: gvcf_paths must be list/tuple")
        if not gvcf_paths:
            raise ValueError("GVCFCombiner: gvcf_paths must be non-empty")
        for path in gvcf_paths:
            if not isinstance(path, str) or not path:
                raise ValueError(
                    "GVCFCombiner: every gvcf path must be a non-empty string"
                )
        for label, value in (
            ("reference_path", reference_path),
            ("output_gvcf_path", output_gvcf_path),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"GVCFCombiner: {label} must be a non-empty string"
                )
        self._gvcf_paths = tuple(gvcf_paths)
        self._reference_path = reference_path
        self._output_gvcf_path = output_gvcf_path
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> str:
        return self._output_gvcf_path

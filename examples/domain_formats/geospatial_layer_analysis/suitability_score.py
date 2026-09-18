"""``SuitabilityScore`` — the final graded verdict for one feature.

Part of the ``examples.domain_formats.geospatial_layer_analysis`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SuitabilityScore:
    feature_id: str
    score: float
    grade: str
    factors: dict[str, str]
    signals_used: list[str]
    signals_missing: list[str]

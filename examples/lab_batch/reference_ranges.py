"""``ReferenceRanges`` — the biomarker reference intervals the analysis knot checks against.

Part of the ``examples.lab_batch`` example.
"""

from __future__ import annotations

from typing import ClassVar


class ReferenceRanges:
    """Normal (low, high) interval for every biomarker in the panel."""

    by_marker: ClassVar[dict[str, tuple[float, float]]] = {
        "haemoglobin": (120.0, 180.0),  # g/L
        "white_cells": (4.0, 11.0),  # x10^9/L
        "platelets": (150.0, 400.0),  # x10^9/L
        "creatinine": (60.0, 110.0),  # µmol/L
        "glucose": (3.9, 6.1),  # mmol/L
    }

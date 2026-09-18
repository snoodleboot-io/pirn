"""``QualityReport``

Part of the ``examples.software_execution.ci_pipeline`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class QualityReport:
    tool: str
    issues: int
    duration_ms: float

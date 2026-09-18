"""``TestReport``

Part of the ``examples.software_execution.ci_pipeline`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TestReport:
    suite: str
    passed: int
    failed: int
    duration_ms: float

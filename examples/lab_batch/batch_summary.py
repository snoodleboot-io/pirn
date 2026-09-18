"""``BatchSummary`` — per-status counts plus every report for one batch.

Part of the ``examples.lab_batch`` example.
"""

from __future__ import annotations

from dataclasses import dataclass

from examples.lab_batch.sample_report import SampleReport


@dataclass
class BatchSummary:
    total: int
    normal: int
    flagged: int
    critical: int
    reports: list[SampleReport]

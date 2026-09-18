"""``CheckoutResult``

Part of the ``examples.software_execution.ci_pipeline`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CheckoutResult:
    commit_sha: str
    branch: str
    files_changed: int

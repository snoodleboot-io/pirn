"""``DeployReceipt``

Part of the ``examples.software_execution.ci_pipeline`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DeployReceipt:
    environment: str
    image_tag: str
    deployed_at: float

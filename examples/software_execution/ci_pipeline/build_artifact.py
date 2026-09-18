"""``BuildArtifact``

Part of the ``examples.software_execution.ci_pipeline`` example.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BuildArtifact:
    image_tag: str
    size_bytes: int

"""``SeededRng`` — deterministic per-study random streams.

Part of the ``examples.domain_formats.medical_triage_agent`` example.
"""

from __future__ import annotations

import hashlib
import random


class SeededRng:
    """Builds a ``random.Random`` seeded from a study id and a stage label.

    Every stage derives its own stream from the same study id, so the example
    is reproducible without threading generator state through the knots.
    """

    @staticmethod
    def for_study(study_id: str, extra: str = "") -> random.Random:
        """Return the stream for ``study_id`` at stage ``extra``."""
        key = f"{study_id}|{extra}"
        seed = int(hashlib.md5(key.encode()).hexdigest(), 16) % (2**32)
        return random.Random(seed)

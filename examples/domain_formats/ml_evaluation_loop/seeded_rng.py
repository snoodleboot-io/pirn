"""``SeededRng`` — deterministic per-model random streams.

Part of the ``examples.domain_formats.ml_evaluation_loop`` example.
"""

from __future__ import annotations

import hashlib
import random


class SeededRng:
    """Builds a ``random.Random`` seeded from a model id and a stage label.

    Architecture, inference and metric noise each draw from their own stream
    derived from the same model id, so a registry sweep is reproducible.
    """

    @staticmethod
    def for_model(model_id: str, extra: str = "") -> random.Random:
        """Return the stream for ``model_id`` at stage ``extra``."""
        key = f"{model_id}|{extra}"
        seed = int(hashlib.md5(key.encode()).hexdigest(), 16) % (2**32)
        return random.Random(seed)

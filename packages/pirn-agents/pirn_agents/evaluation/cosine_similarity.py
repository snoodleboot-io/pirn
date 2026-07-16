"""``cosine_similarity`` — backend-free cosine similarity of two vectors."""

from __future__ import annotations

import math
from collections.abc import Sequence


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Return the cosine similarity of two equal-length numeric vectors.

    Pure Python (no numpy) so embedding-based metrics stay backend-free. A
    zero-magnitude vector yields ``0.0`` (undefined direction treated as
    maximally dissimilar) rather than raising, so an empty-string embedding does
    not crash a metric.

    Args:
        a: The first vector.
        b: The second vector, of the same length as ``a``.

    Returns:
        The cosine similarity in ``[-1.0, 1.0]`` (``0.0`` if either vector has
        zero magnitude).

    Raises:
        ValueError: If the vectors differ in length.
    """
    if len(a) != len(b):
        raise ValueError(
            f"cosine_similarity: vectors must be equal length, got {len(a)} and {len(b)}"
        )
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b, strict=True):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))

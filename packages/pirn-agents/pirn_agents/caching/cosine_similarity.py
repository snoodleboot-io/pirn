"""``cosine_similarity`` — provider-neutral cosine similarity of two vectors.

A single free function shared by the semantic caching paths so near-duplicate
matching is computed identically everywhere. Degenerate input (length mismatch
or a zero-norm vector) yields ``0.0`` rather than raising, so a caller never has
to guard the call site.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """Return the cosine similarity of two equal-length vectors.

    Args:
        left: The first vector.
        right: The second vector.

    Returns:
        The cosine similarity in ``[-1.0, 1.0]``, or ``0.0`` when the vectors
        differ in length or either has zero magnitude.
    """
    if len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    norm_left = math.sqrt(sum(a * a for a in left))
    norm_right = math.sqrt(sum(b * b for b in right))
    if norm_left == 0.0 or norm_right == 0.0:
        return 0.0
    return dot / (norm_left * norm_right)

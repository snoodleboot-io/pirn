"""``EntropyEstimator`` — sample / approximate / permutation entropy.

Algorithm:
    1. Receive the input signal frame, entropy_kind, and embedding_dim.
    2. Validate entropy_kind (one of ``sample``, ``approximate``, ``permutation``,
       ``spectral``) and embedding_dim (positive integer).
    3. Embed the time series in m-dimensional space (where applicable).
    4. Compute the selected entropy measure:
       - ``sample``: SampEn via template matching with tolerance r.
       - ``approximate``: ApEn via similar template matching.
       - ``permutation``: PermEn via ordinal pattern ranking.
       - ``spectral``: SpEn via normalised power spectral entropy.
    5. Return a result mapping with the entropy value and parameters.

Math:
    Sample entropy:

    $$\\text{SampEn}(m, r, N) = -\\ln \\frac{A}{B}$$

    where $A$ = number of template matches of length $m+1$, $B$ = matches of length $m$.

    Spectral entropy:

    $$H_s = -\\sum_k p_k \\ln p_k, \\quad p_k = \\frac{P(f_k)}{\\sum_j P(f_j)}$$

References:
    - Richman, J.S. & Moorman, J.R. (2000). "Physiological time-series analysis using
      approximate entropy and sample entropy." Am. J. Physiol., 278(6), H2039-H2049.
    - antropy library: https://github.com/raphaelvallat/antropy
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import numpy as np

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_payload import SignalPayload


def _sample_entropy(x: np.ndarray, m: int, r: float) -> float:
    """Sample entropy via template matching with Chebyshev distance."""
    n = len(x)

    def _phi(m_val: int) -> int:
        count = 0
        for i in range(n - m_val):
            template = x[i : i + m_val]
            for j in range(n - m_val):
                if i != j and np.max(np.abs(x[j : j + m_val] - template)) < r:
                    count += 1
        return count

    a = _phi(m + 1)
    b = _phi(m)
    if b == 0:
        return 0.0
    return float(-np.log(a / b))


def _approx_entropy(x: np.ndarray, m: int, r: float) -> float:
    """Approximate entropy via template matching (includes self-matches)."""
    n = len(x)

    def _phi(m_val: int) -> float:
        counts = []
        for i in range(n - m_val + 1):
            template = x[i : i + m_val]
            c = sum(
                1 for j in range(n - m_val + 1) if np.max(np.abs(x[j : j + m_val] - template)) <= r
            )
            counts.append(float(c) / (n - m_val + 1))
        return float(np.mean(np.log(counts)))

    return float(_phi(m) - _phi(m + 1))


def _perm_entropy(x: np.ndarray, m: int) -> float:
    """Permutation entropy via ordinal pattern frequencies."""
    n = len(x)
    counts: dict[tuple[int, ...], int] = {}
    for i in range(n - m + 1):
        pattern = tuple(int(r) for r in np.argsort(x[i : i + m]))
        counts[pattern] = counts.get(pattern, 0) + 1
    total = sum(counts.values())
    probs = np.array([v / total for v in counts.values()])
    return float(-np.sum(probs * np.log(probs + 1e-12)))


def _spectral_entropy(x: np.ndarray) -> float:
    """Shannon entropy over the normalised power spectrum."""
    power = np.abs(np.fft.rfft(x)) ** 2
    power_sum = power.sum()
    if power_sum == 0.0:
        return 0.0
    p = power / power_sum
    return float(-np.sum(p * np.log(p + 1e-12)))


def _compute_entropy(x: np.ndarray, kind: str, m: int) -> float:
    """Dispatch entropy computation to the selected measure."""
    r = 0.2 * float(np.std(x))
    if kind == "sample":
        return _sample_entropy(x, m, r)
    if kind == "approximate":
        return _approx_entropy(x, m, r)
    if kind == "permutation":
        return _perm_entropy(x, m)
    return _spectral_entropy(x)


class EntropyEstimator(Knot):
    """Time-series complexity / entropy estimator."""

    _valid_kinds = frozenset({"sample", "approximate", "permutation", "spectral"})

    def __init__(
        self,
        *,
        signal: Knot,
        entropy_kind: Knot | str,
        embedding_dim: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            entropy_kind=entropy_kind,
            embedding_dim=embedding_dim,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalPayload,
        entropy_kind: str,
        embedding_dim: int,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Compute the configured entropy measure from the signal.

        Args:
            signal: Signal payload to measure entropy from.
            entropy_kind: One of ``sample``, ``approximate``, ``permutation``, ``spectral``.
            embedding_dim: Embedding dimension for template matching (positive integer).

        Returns:
            Mapping containing ``signal_id``, ``entropy_kind``, ``value``, and ``embedding_dim``.

        Raises:
            ValueError: If entropy_kind or embedding_dim are invalid.
        """
        if entropy_kind not in self._valid_kinds:
            raise ValueError(
                "EntropyEstimator: entropy_kind must be 'sample', 'approximate', "
                "'permutation', or 'spectral'"
            )
        if not isinstance(embedding_dim, int) or embedding_dim <= 0:
            raise ValueError("EntropyEstimator: embedding_dim must be a positive integer")
        x = signal.data[0] if signal.data.ndim > 1 else signal.data
        value = await asyncio.to_thread(
            _compute_entropy, x.astype(float), entropy_kind, embedding_dim
        )
        return {
            "signal_id": signal.frame.signal_id,
            "entropy_kind": entropy_kind,
            "value": value,
            "embedding_dim": embedding_dim,
        }

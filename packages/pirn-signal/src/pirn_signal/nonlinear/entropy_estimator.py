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

from pirn_signal.types.signal_payload import SignalPayload


def _sample_entropy(signal_array: np.ndarray, template_length: int, tolerance: float) -> float:
    """Sample entropy via template matching with Chebyshev distance."""
    signal_length = len(signal_array)

    def _phi(m_val: int) -> int:
        count = 0
        for template_idx in range(signal_length - m_val):
            template = signal_array[template_idx : template_idx + m_val]
            for compare_idx in range(signal_length - m_val):
                if (
                    template_idx != compare_idx
                    and np.max(np.abs(signal_array[compare_idx : compare_idx + m_val] - template))
                    < tolerance
                ):
                    count += 1
        return count

    match_count_longer = _phi(template_length + 1)
    match_count_base = _phi(template_length)
    if match_count_base == 0:
        return 0.0
    return float(-np.log(match_count_longer / match_count_base))


def _approx_entropy(signal_array: np.ndarray, template_length: int, tolerance: float) -> float:
    """Approximate entropy via template matching (includes self-matches)."""
    signal_length = len(signal_array)

    def _phi(m_val: int) -> float:
        counts = []
        for template_idx in range(signal_length - m_val + 1):
            template = signal_array[template_idx : template_idx + m_val]
            match_count = sum(
                1
                for compare_idx in range(signal_length - m_val + 1)
                if np.max(np.abs(signal_array[compare_idx : compare_idx + m_val] - template))
                <= tolerance
            )
            counts.append(float(match_count) / (signal_length - m_val + 1))
        return float(np.mean(np.log(counts)))

    return float(_phi(template_length) - _phi(template_length + 1))


def _perm_entropy(signal_array: np.ndarray, template_length: int) -> float:
    """Permutation entropy via ordinal pattern frequencies."""
    signal_length = len(signal_array)
    counts: dict[tuple[int, ...], int] = {}
    for start_idx in range(signal_length - template_length + 1):
        pattern = tuple(
            int(rank) for rank in np.argsort(signal_array[start_idx : start_idx + template_length])
        )
        counts[pattern] = counts.get(pattern, 0) + 1
    total = sum(counts.values())
    probs = np.array([v / total for v in counts.values()])
    return float(-np.sum(probs * np.log(probs + 1e-12)))


def _spectral_entropy(signal_array: np.ndarray) -> float:
    """Shannon entropy over the normalised power spectrum."""
    power = np.abs(np.fft.rfft(signal_array)) ** 2
    power_sum = power.sum()
    if power_sum == 0.0:
        return 0.0
    probabilities = power / power_sum
    return float(-np.sum(probabilities * np.log(probabilities + 1e-12)))


def _compute_entropy(signal_array: np.ndarray, kind: str, template_length: int) -> float:
    """Dispatch entropy computation to the selected measure."""
    tolerance = 0.2 * float(np.std(signal_array))
    if kind == "sample":
        return _sample_entropy(signal_array, template_length, tolerance)
    if kind == "approximate":
        return _approx_entropy(signal_array, template_length, tolerance)
    if kind == "permutation":
        return _perm_entropy(signal_array, template_length)
    return _spectral_entropy(signal_array)


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
        signal_array = signal.data[0] if signal.data.ndim > 1 else signal.data
        value = await asyncio.to_thread(
            _compute_entropy, signal_array.astype(float), entropy_kind, embedding_dim
        )
        return {
            "signal_id": signal.frame.signal_id,
            "entropy_kind": entropy_kind,
            "value": value,
            "embedding_dim": embedding_dim,
        }

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

from typing import Any, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class EntropyEstimator(Knot):
    """Time-series complexity / entropy estimator.

    Production needs ``antropy`` / ``EntropyHub`` or a hand-rolled
    implementation.
    """

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
        signal: SignalFrame,
        entropy_kind: str,
        embedding_dim: int,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Compute the configured entropy measure from the signal.

        Args:
            signal: Time series signal to measure entropy from.
            entropy_kind: One of ``sample``, ``approximate``, ``permutation``, ``spectral``.
            embedding_dim: Embedding dimension for template matching (positive integer).

        Returns:
            Mapping containing ``signal_id``, ``entropy_kind``, and ``embedding_dim``.

        Raises:
            ValueError: If entropy_kind or embedding_dim are invalid.
        """
        if entropy_kind not in self._valid_kinds:
            raise ValueError(
                "EntropyEstimator: entropy_kind must be 'sample', 'approximate', "
                "'permutation', or 'spectral'"
            )
        if not isinstance(embedding_dim, int) or embedding_dim <= 0:
            raise ValueError(
                "EntropyEstimator: embedding_dim must be a positive integer"
            )
        return {
            "signal_id": signal.signal_id,
            "entropy_kind": entropy_kind,
            "embedding_dim": embedding_dim,
        }

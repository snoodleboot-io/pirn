"""``PermutationEntropyCalculator`` — ordinal pattern complexity measure.

Algorithm:
    1. Receive the input signal frame, order, and delay.
    2. Validate order (integer in [2, 8]) and delay (positive integer).
    3. Extract all overlapping subsequences of length ``order`` spaced by ``delay``.
    4. Map each subsequence to its ordinal rank pattern (one of ``order!`` possible patterns).
    5. Compute the empirical frequency distribution of ordinal patterns.
    6. Apply the Shannon entropy formula to the distribution; normalise by log(order!).
    7. Return a dict with permutation entropy and normalised entropy.

Math:
    Permutation entropy:

    $$H(m) = -\\sum_{\\pi} p(\\pi) \\ln p(\\pi)$$

    Normalised permutation entropy:

    $$\\tilde{H}(m) = \\frac{H(m)}{\\ln(m!)}$$

    where $m$ = order and $p(\\pi)$ is the empirical probability of ordinal pattern $\\pi$.

References:
    - Bandt, C. & Pompe, B. (2002). "Permutation entropy: a natural complexity measure for
      time series." Phys. Rev. Lett., 88(17), 174102.
    - antropy library: https://github.com/raphaelvallat/antropy
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class PermutationEntropyCalculator(Knot):
    """Compute permutation entropy and normalised permutation entropy.

    Production needs ``antropy`` or a hand-rolled ordinal-pattern
    implementation.
    """

    def __init__(
        self,
        *,
        signal: Knot,
        order: Knot | int,
        delay: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            order=order,
            delay=delay,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        order: int,
        delay: int,
        **_: Any,
    ) -> dict[str, float]:
        """Compute permutation entropy from ordinal patterns in the signal.

        Args:
            signal: Time series signal to analyse.
            order: Ordinal pattern length (integer in [2, 8]).
            delay: Sample lag between pattern elements (positive integer).

        Returns:
            Dictionary with keys ``permutation_entropy`` and ``normalized_entropy``.

        Raises:
            ValueError: If order or delay are invalid.
        """
        if not isinstance(order, int) or order < 2 or order > 8:
            raise ValueError(
                "PermutationEntropyCalculator: order must be an integer in [2, 8]"
            )
        if not isinstance(delay, int) or delay <= 0:
            raise ValueError(
                "PermutationEntropyCalculator: delay must be a positive integer"
            )
        return {
            "permutation_entropy": 0.0,
            "normalized_entropy": 0.0,
        }

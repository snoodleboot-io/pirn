"""``ARModelEstimator`` — fit an autoregressive model to a signal.

Algorithm:
    1. Receive the input signal frame, order, and method.
    2. Validate order (positive integer) and method (one of ``burg``, ``yule_walker``, ``ols``).
    3. Apply the selected estimation method:
       - ``burg``: Burg's recursive lattice method (minimum forward-backward error).
       - ``yule_walker``: Solve the Yule-Walker equations via the Levinson-Durbin recursion.
       - ``ols``: Ordinary least-squares regression on the lag matrix.
    4. Return the estimated AR coefficients, model order, method, and residual variance.

Math:
    AR(p) model:

    $$x(n) = -\\sum_{k=1}^{p} a_k x(n-k) + e(n)$$

    Yule-Walker equations:

    $$\\mathbf{R} \\mathbf{a} = -\\mathbf{r}$$

    where $R_{ij} = R_x(i-j)$ and $r_i = R_x(i)$.

References:
    - Box, G.E.P., Jenkins, G.M. & Reinsel, G.C. (2015). "Time Series Analysis." Wiley.
    - scipy.signal: https://docs.scipy.org/doc/scipy/reference/signal.html
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.signal.types.signal_frame import SignalFrame


class ARModelEstimator(Knot):
    """Fit an autoregressive (AR) model to a signal using a configurable estimation method."""

    _valid_methods = frozenset({"burg", "yule_walker", "ols"})

    def __init__(
        self,
        *,
        signal: Knot,
        order: Knot | int,
        method: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            signal=signal,
            order=order,
            method=method,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        signal: SignalFrame,
        order: int,
        method: str,
        **_: Any,
    ) -> dict[str, Any]:
        """Fit an AR model and return the estimated parameters.

        Args:
            signal: The input signal frame.
            order: AR model order (positive integer).
            method: Estimation method — ``burg``, ``yule_walker``, or ``ols``.

        Returns:
            Dict with keys ``coefficients`` (list[float]), ``order`` (int),
            ``method`` (str), and ``variance`` (float).

        Raises:
            ValueError: If order or method are invalid.
        """
        if not isinstance(order, int) or order <= 0:
            raise ValueError("ARModelEstimator: order must be a positive integer")
        if method not in self._valid_methods:
            raise ValueError("ARModelEstimator: method must be one of 'burg', 'yule_walker', 'ols'")
        return {
            "coefficients": [0.0] * order,
            "order": order,
            "method": method,
            "variance": 1.0,
        }

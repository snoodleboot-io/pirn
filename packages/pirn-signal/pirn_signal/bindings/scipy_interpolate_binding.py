"""``ScipyInterpolateBinding`` — typed boundary over ``scipy.interpolate``.

``scipy`` ships no type stubs. This binding performs the lazy optional-extra
import and exposes one-dimensional interpolation with real ``NDArray``
annotations.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from pirn_signal.signal_optional_dependency import SignalOptionalDependency


class ScipyInterpolateBinding:
    """Annotated facade over the ``scipy.interpolate`` functions used by pirn-signal knots."""

    def __init__(self, module: ModuleType) -> None:
        self._module = module

    @classmethod
    def load(cls) -> ScipyInterpolateBinding:
        """Import ``scipy.interpolate`` lazily through :class:`SignalOptionalDependency`.

        Returns:
            A binding over the imported module.

        Raises:
            ImportError: If ``scipy.interpolate`` is not installed; the message names
                ``pirn-signal[signal]``.
        """
        return cls(SignalOptionalDependency.require("scipy.interpolate", extra="signal"))

    def interp1d_extrapolate(
        self,
        x: ArrayLike,
        y: ArrayLike,
        x_new: ArrayLike,
        kind: str,
        axis: int = -1,
    ) -> NDArray[np.floating[Any]]:
        """Fit ``interp1d(x, y)`` along ``axis`` and evaluate it at ``x_new``, extrapolating.

        Args:
            x: Strictly increasing sample positions.
            y: Sample values; ``axis`` has the same length as ``x``.
            x_new: Positions to evaluate at; points outside ``x`` are extrapolated.
            kind: Interpolation kind understood by ``interp1d`` (``linear``, ``cubic``, ...).
            axis: Axis of ``y`` along which to interpolate.

        Returns:
            The interpolated values at ``x_new``.
        """
        interpolant: Any = self._module.interp1d(
            x, y, kind=kind, axis=axis, fill_value="extrapolate", bounds_error=False
        )
        values: NDArray[np.floating[Any]] = interpolant(x_new)
        return values

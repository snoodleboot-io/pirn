"""``ScipyNdimageBinding`` — typed boundary over ``scipy.ndimage``.

``scipy`` ships no type stubs. This binding performs the lazy optional-extra
import and exposes the ``scipy.ndimage`` calls the knots use with real
``NDArray`` annotations.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from pirn_signal.signal_optional_dependency import SignalOptionalDependency


class ScipyNdimageBinding:
    """Annotated facade over the ``scipy.ndimage`` functions used by pirn-signal knots."""

    def __init__(self, module: ModuleType) -> None:
        self._module = module

    @classmethod
    def load(cls) -> ScipyNdimageBinding:
        """Import ``scipy.ndimage`` lazily through :class:`SignalOptionalDependency`.

        Returns:
            A binding over the imported module.

        Raises:
            ImportError: If ``scipy.ndimage`` is not installed; the message names
                ``pirn-signal[signal]``.
        """
        return cls(SignalOptionalDependency.require("scipy.ndimage", extra="signal"))

    def median_filter(
        self, data: ArrayLike, size: int | tuple[int, ...]
    ) -> NDArray[np.floating[Any]]:
        """Apply a sliding median of footprint ``size``; the output has the input's shape."""
        filtered: NDArray[np.floating[Any]] = self._module.median_filter(data, size=size)
        return filtered

"""``VmdpyBinding`` — typed boundary over ``vmdpy``.

vmdpy ships no type stubs. This binding performs the lazy optional-extra import and exposes variational mode
decomposition with real ``NDArray`` annotations.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any

import numpy as np
from numpy.typing import NDArray
from pirn.core.optional_dependency import OptionalDependency


class VmdpyBinding:
    """Annotated facade over ``vmdpy.VMD``."""

    def __init__(self, module: ModuleType) -> None:
        self._module = module

    @classmethod
    def load(cls) -> VmdpyBinding:
        """Import ``vmdpy`` lazily through :class:`OptionalDependency`.

        Returns:
            A binding over the imported module.

        Raises:
            ImportError: If ``vmdpy`` is not installed; the message names
                ``pirn-signal[signal]``.
        """
        return cls(OptionalDependency.require("vmdpy", extra="signal", package="pirn-signal"))

    def vmd(
        self, signal_array: NDArray[np.floating[Any]], alpha: float, mode_count: int
    ) -> NDArray[np.float64]:
        """Variational mode decomposition of a 1-D signal; returns modes shaped ``(K, samples)``.

        Runs the reference ADMM solver with no time-step noise slack (``tau=0``), no
        DC mode, uniformly initialised centre frequencies and a ``1e-7`` tolerance.
        """
        modes, _modes_hat, _omega = self._module.VMD(
            signal_array, alpha, tau=0, K=mode_count, DC=0, init=1, tol=1e-7
        )
        result: NDArray[np.float64] = modes
        return result

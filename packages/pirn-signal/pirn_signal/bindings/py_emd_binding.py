"""``PyEmdBinding`` — typed boundary over ``PyEMD`` (the EMD-signal distribution).

EMD-signal ships no type stubs. This binding performs the lazy optional-extra
import and exposes empirical mode decomposition and its ensemble variant with
real ``NDArray`` annotations.
"""

from __future__ import annotations

from types import ModuleType
from typing import Any

import numpy as np
from numpy.typing import NDArray
from pirn.core.optional_dependency import OptionalDependency


class PyEmdBinding:
    """Annotated facade over the ``PyEMD`` decompositions used by pirn-signal knots."""

    def __init__(self, module: ModuleType) -> None:
        self._module = module

    @classmethod
    def load(cls) -> PyEmdBinding:
        """Import ``PyEMD`` lazily through :class:`OptionalDependency`.

        Returns:
            A binding over the imported module.

        Raises:
            ImportError: If ``PyEMD`` is not installed; the message names
                ``pirn-signal[emd]``.
        """
        return cls(OptionalDependency.require("PyEMD", extra="emd", package="pirn-signal"))

    def emd(self, channel: NDArray[np.floating[Any]], max_imf: int) -> NDArray[np.float64]:
        """Empirical mode decomposition of a 1-D signal; returns IMFs shaped ``(imfs, samples)``."""
        decomposer: Any = self._module.EMD()
        imfs: NDArray[np.float64] = decomposer.emd(channel, max_imf=max_imf)
        return imfs

    def eemd(
        self,
        channel: NDArray[np.floating[Any]],
        trials: int,
        noise_width: float,
        max_imf: int,
    ) -> NDArray[np.float64]:
        """Ensemble EMD of a 1-D signal; returns IMFs shaped ``(imfs, samples)``."""
        decomposer: Any = self._module.EEMD(trials=trials, noise_width=noise_width)
        imfs: NDArray[np.float64] = decomposer.eemd(channel, max_imf=max_imf)
        return imfs

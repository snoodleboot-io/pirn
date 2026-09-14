"""``PyWaveletsBinding`` — typed boundary over ``pywt`` (PyWavelets).

PyWavelets ships no type stubs; strict pyright reports its functions as
partially unknown. This binding performs the lazy optional-extra import and
exposes the discrete, stationary, continuous and packet transforms the knots
use with real ``NDArray`` annotations.
"""

from __future__ import annotations

from collections.abc import Sequence
from types import ModuleType
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray
from pirn.core.optional_dependency import OptionalDependency


class PyWaveletsBinding:
    """Annotated facade over the ``pywt`` functions used by pirn-signal knots."""

    def __init__(self, module: ModuleType) -> None:
        self._module = module

    @classmethod
    def load(cls) -> PyWaveletsBinding:
        """Import ``pywt`` lazily through :class:`OptionalDependency`.

        Returns:
            A binding over the imported module.

        Raises:
            ImportError: If ``pywt`` is not installed; the message names
                ``pirn-signal[signal]``.
        """
        return cls(OptionalDependency.require("pywt", extra="signal", package="pirn-signal"))

    def wavedec(
        self, data: ArrayLike, wavelet: str, level: int, axis: int = -1
    ) -> list[NDArray[np.floating[Any]]]:
        """Multilevel DWT; returns ``[cA_n, cD_n, ..., cD_1]``."""
        coefficients: list[NDArray[np.floating[Any]]] = list(
            self._module.wavedec(data, wavelet, level=level, axis=axis)
        )
        return coefficients

    def waverec(
        self, coefficients: Sequence[ArrayLike], wavelet: str, axis: int = -1
    ) -> NDArray[np.floating[Any]]:
        """Multilevel inverse DWT of ``[cA_n, cD_n, ..., cD_1]``."""
        reconstructed: NDArray[np.floating[Any]] = self._module.waverec(
            list(coefficients), wavelet, axis=axis
        )
        return reconstructed

    def threshold(self, data: ArrayLike, value: float, mode: str) -> NDArray[np.floating[Any]]:
        """Threshold ``data`` at ``value`` (``soft``, ``hard``, ``garrote``, ...)."""
        thresholded: NDArray[np.floating[Any]] = self._module.threshold(data, value, mode=mode)
        return thresholded

    def swt(
        self, data: ArrayLike, wavelet: str, level: int, axis: int = -1
    ) -> list[tuple[NDArray[np.floating[Any]], NDArray[np.floating[Any]]]]:
        """Multilevel stationary wavelet transform; returns ``[(cA_n, cD_n), ..., (cA_1, cD_1)]``."""
        pairs: list[tuple[NDArray[np.floating[Any]], NDArray[np.floating[Any]]]] = list(
            self._module.swt(data, wavelet, level=level, axis=axis)
        )
        return pairs

    def cwt(
        self,
        data: ArrayLike,
        scales: ArrayLike,
        wavelet: str,
        sampling_period: float,
        axis: int = -1,
    ) -> tuple[NDArray[np.inexact[Any]], NDArray[np.float64]]:
        """Continuous wavelet transform; returns ``(coefficients, frequencies)``.

        ``coefficients`` has the scale axis first; it is complex for complex wavelets.
        """
        result: tuple[NDArray[np.inexact[Any]], NDArray[np.float64]] = self._module.cwt(
            data, scales, wavelet, sampling_period=sampling_period, axis=axis
        )
        return result

    def wavelet_packet_level(
        self, data: ArrayLike, wavelet: str, level: int
    ) -> list[NDArray[np.floating[Any]]]:
        """Decompose ``data`` into a wavelet packet tree; return level ``level`` in frequency order."""
        packet: Any = self._module.WaveletPacket(data, wavelet, maxlevel=level)
        nodes: list[Any] = list(packet.get_level(level, "freq"))
        bands: list[NDArray[np.floating[Any]]] = [node.data for node in nodes]
        return bands

"""``SoundfileBinding`` — typed boundary over ``soundfile``.

soundfile ships no type stubs. This binding performs the lazy import (soundfile
arrives with the ``signal`` extra through librosa) and exposes WAV encoding with
real annotations.
"""

from __future__ import annotations

import io
from types import ModuleType
from typing import Any

import numpy as np
from numpy.typing import NDArray
from pirn.core.optional_dependency import OptionalDependency


class SoundfileBinding:
    """Annotated facade over the ``soundfile`` calls used by pirn-signal knots."""

    def __init__(self, module: ModuleType) -> None:
        self._module = module

    @classmethod
    def load(cls) -> SoundfileBinding:
        """Import ``soundfile`` lazily through :class:`OptionalDependency`.

        Returns:
            A binding over the imported module.

        Raises:
            ImportError: If ``soundfile`` is not installed; the message names
                ``pirn-signal[signal]``.
        """
        return cls(OptionalDependency.require("soundfile", extra="signal", package="pirn-signal"))

    def write_float_wav(
        self, buffer: io.BytesIO, audio: NDArray[np.floating[Any]], sample_rate_hz: int
    ) -> None:
        """Encode ``audio`` (``(frames,)`` or ``(frames, channels)``) as 32-bit float WAV into ``buffer``."""
        self._module.write(buffer, audio, samplerate=sample_rate_hz, format="WAV", subtype="FLOAT")

"""``SignalOptionalDependency`` — lazy import of an optional pirn-signal extra.

The DSP backends (scipy, PyWavelets, EMD-signal, vmdpy, scikit-learn, soundfile)
are optional extras and ship no type stubs. Importing them through
``importlib`` at the call boundary keeps ``import pirn_signal`` free of heavy
dependencies, raises one uniform ``ImportError`` naming the extra to install,
and hands back a plain ``ModuleType`` whose attributes callers convert to
precise types immediately (see ``pirn_signal.bindings``).
"""

from __future__ import annotations

import importlib
from types import ModuleType


class SignalOptionalDependency:
    """Lazily import a module provided by a ``pirn-signal`` optional extra."""

    @staticmethod
    def require(module: str, *, extra: str) -> ModuleType:
        """Import ``module``, or explain which extra provides it.

        Args:
            module: Dotted module name to import (e.g. ``"scipy.signal"``).
            extra: The ``pirn-signal`` optional extra that installs it (e.g. ``"signal"``).

        Returns:
            The imported module.

        Raises:
            ImportError: If ``module`` cannot be imported; the message names the
                module and the ``pip install pirn-signal[<extra>]`` command.
        """
        try:
            return importlib.import_module(module)
        except ImportError as exc:
            raise ImportError(
                f"pirn-signal requires '{module}'. Install via pip install pirn-signal[{extra}]"
            ) from exc

"""``MlOptionalDependency`` — lazy import of an optional third-party module.

pirn-ml keeps optional SDKs (``joblib`` and friends, installed through an
extra) out of module import time. A knot that needs one asks for it at call
time; a missing module surfaces as an :class:`ImportError` naming the extra
that provides it. The returned :class:`~types.ModuleType` is untyped, so every
value read off it is converted to a precise type at the call site.
"""

from __future__ import annotations

import importlib
from types import ModuleType


class MlOptionalDependency:
    """Lazy importer for the optional dependencies behind pirn-ml's extras."""

    @staticmethod
    def require(module: str, *, extra: str) -> ModuleType:
        """Import ``module`` now, or explain which pirn-ml extra installs it.

        Args:
            module: Dotted module name to import (e.g. ``"joblib"``).
            extra: The pirn-ml extra that provides the module (e.g. ``"ml"``).

        Returns:
            The imported module.

        Raises:
            ImportError: If the module is not installed; the message names
                ``pirn-ml[<extra>]``.
        """
        try:
            return importlib.import_module(module)
        except ImportError as exc:
            raise ImportError(
                f"{module} is not installed; install it with `pip install pirn-ml[{extra}]`"
            ) from exc

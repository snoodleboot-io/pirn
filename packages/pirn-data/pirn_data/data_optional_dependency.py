"""``DataOptionalDependency`` — lazy import of an optional pirn-data extra.

pirn-data's engines and adapters sit behind optional extras (``pirn-data[delta]``,
``pirn-data[lance]``, ...). A knot that needs one imports it at call time, not at
module import, so the package imports cleanly without the extra installed. This
helper is that one import seam: it returns the module and turns a missing extra
into an :class:`ImportError` that names the exact ``pip install`` command.

The module comes back as :class:`types.ModuleType`, whose attributes are ``Any``
to a type checker — whether or not the extra is installed where the checker
runs. Callers convert what they read off it to precise types immediately.

References:
    [1] Python docs — importlib.import_module:
        https://docs.python.org/3/library/importlib.html#importlib.import_module
"""

from __future__ import annotations

import importlib
from types import ModuleType


class DataOptionalDependency:
    """Import optional third-party modules lazily, naming the extra when absent."""

    @staticmethod
    def require(module: str, *, extra: str) -> ModuleType:
        """Import ``module``, raising a friendly error if the extra is missing.

        Args:
            module: The importable module name (e.g. ``"deltalake"``).
            extra: The pirn-data extra that provides it (e.g. ``"delta"``).

        Returns:
            The imported module.

        Raises:
            ImportError: If ``module`` cannot be imported. The message names
                ``pip install "pirn-data[<extra>]"``.
        """
        try:
            return importlib.import_module(module)
        except ImportError as exc:
            raise ImportError(
                f"{module!r} is required for this feature; install it with: "
                f'pip install "pirn-data[{extra}]"'
            ) from exc

"""``HealthOptionalDependency`` — lazy import of an optional pirn-health SDK.

The health knots call scientific SDKs that ship in the package's optional
extras (``scipy``, ``scikit-learn``, ``nibabel``, ``dipy``, ``SimpleITK``,
``pydicom``). None of them is imported at module load: a knot resolves the
module it needs inside the method that uses it, through :meth:`require`, so

* ``import pirn_health`` and registry discovery work without any extra, and a
  missing extra surfaces as one ``ImportError`` naming the exact
  ``pip install`` command, at the call that needs it;
* the knot module carries no ``_HAS_X`` flag and no ``X = None`` fallback
  binding that the type checker would have to be told to ignore.

Most of these SDKs publish no type information (no stubs, no ``py.typed``), so
the returned module is used as the untyped boundary it is: every value read off
it is bound to a precisely annotated local (``np.ndarray``, ``float``, ...) at
the call site, which is where the typed code resumes.

Algorithm:
    1. Import ``module`` with :func:`importlib.import_module`.
    2. On ``ImportError`` raise a new ``ImportError`` naming the module and
       ``pip install 'pirn-health[<extra>]'``, chained to the cause.
"""

from __future__ import annotations

import importlib
from types import ModuleType


class HealthOptionalDependency:
    """Namespace for the lazy optional-SDK import used by pirn-health knots."""

    @staticmethod
    def require(module: str, *, extra: str) -> ModuleType:
        """Import ``module``, raising an install hint if its extra is missing.

        Args:
            module: Dotted module name to import (e.g. ``"scipy.signal"``).
            extra: The pirn-health optional extra that provides it (e.g. ``"health"``).

        Returns:
            The imported module.

        Raises:
            ImportError: If ``module`` cannot be imported. The message names
                ``module`` and ``pip install 'pirn-health[<extra>]'``.
        """
        try:
            return importlib.import_module(module)
        except ImportError as exc:
            raise ImportError(
                f"{module!r} is required; install it with: pip install 'pirn-health[{extra}]'"
            ) from exc

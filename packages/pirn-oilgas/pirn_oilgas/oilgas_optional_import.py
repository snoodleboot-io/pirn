"""``OilgasOptionalImport`` — the typed boundary for the ``oilgas`` extra's SDKs.

``lasio``, ``segyio`` and ``scipy`` ship no type stubs (``segyio`` is also absent
from images that skip the extra), so a static ``import`` of them cannot type-check
strictly. Every knot that needs one loads it through :meth:`OilgasOptionalImport.require`,
which imports the module lazily — the knot module itself still imports without the
extra — and turns a missing SDK into an ``ImportError`` naming the install command.

The loaded module is a :class:`types.ModuleType`, so its members are typed ``Any``
at the import; callers narrow what they read back (``np.asarray(..., dtype=...)``,
``int(...)``, ``str(...)``) before it leaves the decode/fit step.
"""

from __future__ import annotations

import importlib
from types import ModuleType


class OilgasOptionalImport:
    """Lazy loader for the SDKs provided by ``pirn-oilgas[oilgas]``."""

    @staticmethod
    def require(module: str, purpose: str) -> ModuleType:
        """Import ``module``, raising a friendly error if the ``oilgas`` extra is missing.

        Args:
            module: The importable module name (e.g. ``"lasio"``, ``"scipy.optimize"``).
            purpose: Who needs it and for what, prefixed to the error message
                (e.g. ``"LasObjectStoreAssembler: decoding LAS bytes"``).

        Returns:
            The imported module.

        Raises:
            ImportError: If ``module`` cannot be imported. The message reads
                ``"<purpose> requires <distribution> — install pirn-oilgas[oilgas]"``.
        """
        try:
            return importlib.import_module(module)
        except ImportError as exc:
            distribution = module.split(".", 1)[0]
            raise ImportError(
                f"{purpose} requires {distribution} — install pirn-oilgas[oilgas]"
            ) from exc

"""``OptionalDependency`` — the one lazy importer for optional third-party backends.

pirn keeps every optional backend (cloud SDKs, database drivers, file-format
libraries, message brokers) out of the import graph until the feature that needs
it runs. :meth:`OptionalDependency.require` is the single place that performs that
lazy import and turns a missing distribution into an actionable ``ImportError``
naming the exact ``pip install`` command.
"""

from __future__ import annotations

import importlib
from types import ModuleType


class OptionalDependency:
    """Lazy import of an optional backend with a uniform install hint."""

    @staticmethod
    def require(module: str, *, extra: str, package: str = "pirn-core") -> ModuleType:
        """Import ``module`` lazily, raising an install hint if it is missing.

        Args:
            module: Dotted module path to import (e.g. ``"httpx"``,
                ``"google.cloud.bigquery"``).
            extra: The pip extra of ``package`` that installs ``module``.
            package: The distribution that declares ``extra``. Defaults to
                ``"pirn-core"``; domain packages pass their own name.

        Returns:
            The imported module.

        Raises:
            TypeError: If ``module``, ``extra`` or ``package`` is not a ``str``.
            ValueError: If ``module``, ``extra`` or ``package`` is empty.
            ImportError: If ``module`` cannot be imported. The message names
                ``pip install "<package>[<extra>]"`` and chains the original
                error.
        """
        for name, value in (("module", module), ("extra", extra), ("package", package)):
            if not isinstance(value, str):
                raise TypeError(f"{name} must be a str, got {type(value).__name__}")
            if not value:
                raise ValueError(f"{name} must be a non-empty str")
        try:
            return importlib.import_module(module)
        except ImportError as exc:
            raise ImportError(
                f"{module!r} is required for this feature; install it with: "
                f'pip install "{package}[{extra}]"'
            ) from exc

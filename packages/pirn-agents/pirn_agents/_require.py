"""Shared lazy-import helper for optional backend dependencies.

Every connector or tool that needs an optional backend imports it through
:func:`_require`, which turns a missing backend into a friendly ``ImportError``
that names the exact ``pip install`` command needed to provision it.
"""

from __future__ import annotations

import importlib
from types import ModuleType


def _require(extra: str, module: str) -> ModuleType:
    """Import ``module``, raising a friendly error if its backend is missing.

    Args:
        extra: The optional-dependency extra that provides ``module`` (e.g.
            ``"web"`` for the ``httpx`` backend).
        module: The importable module name (e.g. ``"httpx"``).

    Returns:
        The imported module.

    Raises:
        ImportError: If ``module`` cannot be imported. The message names the
            exact command ``pip install "pirn-agents[{extra}]"``.
    """
    try:
        return importlib.import_module(module)
    except ImportError as exc:
        raise ImportError(
            f"{module!r} is required for this feature; install it with: "
            f'pip install "pirn-agents[{extra}]"'
        ) from exc

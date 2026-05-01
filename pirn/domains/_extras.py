"""Helpers for domain modules to surface a clean ``ImportError`` when their
optional extras are not installed.

Every domain ``__init__.py`` calls :func:`require_extra` at import time so that
``import pirn.domains.health`` (without ``pip install pirn[health]``) fails fast
with an actionable message rather than a cryptic ``ModuleNotFoundError`` deep
inside a knot.
"""

from __future__ import annotations

from importlib.util import find_spec


def require_extra(extra_name: str, modules: list[str]) -> None:
    """Raise ``ImportError`` listing missing modules for an extra.

    Parameters
    ----------
    extra_name:
        The pip extra to install (e.g. ``"health"``); used in the install hint.
    modules:
        Top-level module names that the extra is expected to provide.
        Every entry is checked; the error lists all missing ones together.
    """
    missing = [m for m in modules if find_spec(m) is None]
    if not missing:
        return
    pretty = ", ".join(missing)
    raise ImportError(
        f"pirn.domains.{extra_name} requires {pretty}. "
        f"Install with: pip install 'pirn[{extra_name}]'"
    )

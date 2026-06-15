"""Per-domain optional-extras loader for ``pirn_ml``.

The ``pirn_ml`` package instantiates :class:`ExtrasLoader` with its
required modules and calls :meth:`ExtrasLoader.require` at the call boundary
so missing dependencies surface as a clear ``ImportError`` with the install
hint instead of a cryptic ``ModuleNotFoundError`` deep in a knot.
"""

from __future__ import annotations

from importlib.util import find_spec


class ExtrasLoader:
    """Verifies a list of optional dependencies are importable.

    Construct one per extra and call :meth:`require` before using a
    dependency-bound knot. Subclasses are not expected — the configuration is
    constructor-driven.
    """

    def __init__(self, extra_name: str, modules: list[str]) -> None:
        self._extra_name = extra_name
        self._modules = list(modules)

    @property
    def extra_name(self) -> str:
        return self._extra_name

    @property
    def modules(self) -> tuple[str, ...]:
        return tuple(self._modules)

    def require(self) -> None:
        """Raise ``ImportError`` listing every missing module.

        No-op when every configured module resolves. The error message is
        actionable — names every missing module and shows the exact
        ``pip install`` command for the relevant extra.
        """
        missing = [m for m in self._modules if find_spec(m) is None]
        if not missing:
            return
        pretty = ", ".join(missing)
        raise ImportError(
            f"pirn_ml[{self._extra_name}] requires {pretty}. "
            f"Install with: pip install 'pirn-ml[{self._extra_name}]'"
        )

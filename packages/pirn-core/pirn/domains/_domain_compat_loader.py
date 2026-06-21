"""Loader half of the ``pirn.domains`` compatibility import hook.

Paired with :class:`pirn.domains._domain_compat_finder.DomainCompatFinder`.
``create_module`` returns the backing ``pirn_<x>`` module (already executed
under its canonical name) so the import system installs that real module
object under the legacy ``pirn.domains.<x>`` name; ``exec_module`` is a no-op
because the backing module is already executed.
"""

from __future__ import annotations

from importlib.abc import Loader
from importlib.machinery import ModuleSpec
from types import ModuleType


class DomainCompatLoader(Loader):
    """Aliasing loader for legacy ``pirn.domains.<x>[.<sub>]`` names."""

    def create_module(self, spec: ModuleSpec) -> ModuleType:
        # Deferred import avoids a finder<->loader import cycle: the finder
        # module imports this loader at module top, so this loader may only
        # reach back into the finder lazily, at call time.
        from pirn.domains._domain_compat_finder import DomainCompatFinder

        return DomainCompatFinder.import_legacy(spec.name)

    def exec_module(self, module: ModuleType) -> None:
        del module

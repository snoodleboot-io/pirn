"""Import-system hook that maps legacy ``pirn.domains.<x>`` to ``pirn_<x>``.

The six pirn domains were extracted into standalone distributions
(``pirn_signal``, ``pirn_oilgas``, ``pirn_data``, ``pirn_ml``, ``pirn_agents``,
``pirn_health``). Legacy code that imports them under the old
``pirn.domains.<x>`` paths keeps working through this
:class:`importlib.abc.MetaPathFinder`, which defers to the installed
``pirn_<x>`` package and emits a :class:`DeprecationWarning`.

Core never imports any domain at module level — resolution is entirely
deferred through :mod:`importlib`, so core retains zero hard dependency on
any domain package.
"""

from __future__ import annotations

import importlib
import sys
import warnings
from importlib.abc import MetaPathFinder
from importlib.machinery import ModuleSpec
from importlib.util import find_spec
from types import ModuleType
from typing import TYPE_CHECKING

from pirn.domains._domain_compat_loader import DomainCompatLoader

if TYPE_CHECKING:
    from collections.abc import Sequence


class DomainCompatFinder(MetaPathFinder):
    """Resolve ``pirn.domains.<x>[.<sub>]`` to the installed ``pirn_<x>``.

    Registered (appended) on :data:`sys.meta_path` so it only fires for the
    legacy compat names that real finders miss. For a recognised domain it
    imports the target ``pirn_<x>`` module, aliases it into
    :data:`sys.modules` under the legacy name, and emits a single
    :class:`DeprecationWarning` for the top-level domain. When the backing
    package is absent it raises an actionable :class:`ImportError` naming the
    ``pip install pirn-<x>`` fix.
    """

    legacy_prefix = "pirn.domains."
    domains: tuple[str, ...] = (
        "agents",
        "data",
        "health",
        "ml",
        "oilgas",
        "signal",
    )

    @classmethod
    def register(cls) -> None:
        """Insert a single finder instance at the front of :data:`sys.meta_path`.

        Idempotent: a finder of this class already present is left in place,
        so re-import or module reload never stacks duplicates.

        It must sit ahead of the standard ``PathFinder``: once a legacy
        ``pirn.domains.<x>`` name is aliased to its ``pirn_<x>`` package, that
        package exposes a ``__path__``, so an *appended* finder would let
        ``PathFinder`` resolve legacy submodules (``pirn.domains.<x>.<sub>``)
        off that path and execute them under the legacy ``__name__`` — clobbering
        the real ``pirn_<x>.<sub>`` module identity (and every class
        ``__module__``). Resolving first keeps submodules loaded under their
        canonical ``pirn_<x>`` names. Non-legacy names short-circuit to ``None``.
        """
        if any(isinstance(finder, cls) for finder in sys.meta_path):
            return
        sys.meta_path.insert(0, cls())

    @classmethod
    def resolve_target(cls, fullname: str) -> str | None:
        """Map a legacy ``pirn.domains.<x>[.<sub>]`` name to ``pirn_<x>[.<sub>]``.

        Returns ``None`` when ``fullname`` is not under a recognised domain so
        the caller can fall through to normal resolution (and real
        :class:`AttributeError` / :class:`ImportError` semantics).
        """
        if not fullname.startswith(cls.legacy_prefix):
            return None
        remainder = fullname[len(cls.legacy_prefix) :]
        domain, _, sub = remainder.partition(".")
        if domain not in cls.domains:
            return None
        target = f"pirn_{domain}"
        return f"{target}.{sub}" if sub else target

    @classmethod
    def import_legacy(cls, fullname: str) -> ModuleType:
        """Import and alias the backing module for a legacy domain name.

        Emits the deprecation warning, raises an actionable
        :class:`ImportError` when the backing package is absent, and binds the
        resolved module into :data:`sys.modules` under ``fullname``.
        """
        target = cls.resolve_target(fullname)
        if target is None:
            raise ModuleNotFoundError(fullname, name=fullname)

        domain = fullname[len(cls.legacy_prefix) :].partition(".")[0]
        cls._warn(domain)

        if find_spec(f"pirn_{domain}") is None:
            raise ImportError(
                f"pirn.domains.{domain} is a compatibility alias for the "
                f"standalone 'pirn_{domain}' package, which is not installed. "
                f"Install it with: pip install pirn-{domain}",
                name=fullname,
            )

        module = importlib.import_module(target)
        sys.modules[fullname] = module
        return module

    @classmethod
    def _warn(cls, domain: str) -> None:
        warnings.warn(
            f"'pirn.domains.{domain}' is deprecated; the domain now ships as "
            f"the standalone 'pirn_{domain}' package. Import 'pirn_{domain}' "
            f"directly, or run the 'pirn-migrate-imports' codemod.",
            DeprecationWarning,
            stacklevel=3,
        )

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None = None,
        target: ModuleType | None = None,
    ) -> ModuleSpec | None:
        """Return a spec whose loader aliases the backing ``pirn_<x>`` module.

        Returns ``None`` for any name this finder does not own, letting the
        import machinery raise its normal ``ModuleNotFoundError``.
        """
        del path, target
        resolved = self.resolve_target(fullname)
        if resolved is None:
            return None
        return ModuleSpec(fullname, DomainCompatLoader())

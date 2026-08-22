"""`import pirn_agents` must pull nothing outside its declared dependencies.

Importing the package runs ``Registry.fill_registry``, which walks and imports
**every knot module in the tree** — 271 modules under ``specializations`` alone.
That makes the import surface unusually wide: a module-level ``import`` of some
third-party package, anywhere in the tree, is executed on a bare
``import pirn_agents``. If that package is not in the declared dependency
closure, a clean install breaks at import time, and it breaks for everyone
rather than only for users of the feature that wanted it.

Nothing is wrong today (PIR-780). The check exists because the failure mode is
invisible in any environment that happens to have the package installed — which
every development environment does — so it would be found by a user, not by CI.

Scope note: this asserts nothing about *cost*. Whether the eager fill should
happen at all is a separate design question, still open on PIR-780.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from importlib.metadata import PackageNotFoundError, packages_distributions, requires

# Injected by the CPython/Cython runtime when a Cython-compiled extension (here,
# numpy) is imported. It is not a distribution and maps to none, so it can never
# be resolved through metadata.
_RUNTIME_ARTEFACTS = frozenset({"cython_runtime"})

# Distributions whose import package cannot be discovered from metadata here.
# Every package in this workspace is installed **editable** — pirn-core ships
# `_editable_impl_pirn_core.pth` rather than real files under site-packages —
# so `packages_distributions()` maps none of its modules and the import name
# has to be stated. It is also not derivable by convention: pirn-core's import
# package is `pirn`, not `pirn_core`.
_DISTRIBUTION_IMPORT_ALIASES = {
    "pirn-core": {"pirn"},
    "pirn-agents": {"pirn_agents"},
}

_PROBE = r"""
import sys
stdlib = set(sys.stdlib_module_names)
before = {m.split(".")[0] for m in sys.modules}
import pirn_agents
after = {m.split(".")[0] for m in sys.modules}
print(__import__("json").dumps(sorted(
    m for m in (after - before)
    if not m.startswith("_") and m not in stdlib and m != "pirn_agents"
)))
"""


def _declared_distributions(root: str = "pirn-agents") -> set[str]:
    """Return ``root``'s transitive run-time distributions, extras excluded.

    Extras are skipped deliberately: an extra is opt-in, so a module it enables
    must not be imported by a bare ``import pirn_agents``.
    """
    seen: set[str] = set()
    queue = [root]
    while queue:
        name = queue.pop()
        key = name.lower().replace("_", "-")
        if key in seen:
            continue
        seen.add(key)
        try:
            reqs = requires(name) or []
        except PackageNotFoundError:  # pragma: no cover - not installed
            continue
        for raw in reqs:
            # Parsed by hand rather than with `packaging.requirements`: this
            # test asserts what the package may import, so leaning on a
            # distribution that pirn-agents does not itself declare would be
            # the very thing it exists to catch.
            marker = raw.split(";", 1)[1] if ";" in raw else ""
            if "extra ==" in marker:
                continue
            match = re.match(r"\s*([A-Za-z0-9._-]+)", raw)
            if match:
                queue.append(match.group(1))
    return seen


def _modules_imported() -> list[str]:
    """Return third-party top-level modules a fresh `import pirn_agents` loads.

    Runs in a subprocess: this test module's own imports would otherwise
    pre-populate ``sys.modules`` and hide exactly what it is looking for.
    """
    completed = subprocess.run(
        [sys.executable, "-c", _PROBE], capture_output=True, text=True, check=True
    )
    return json.loads(completed.stdout.strip().splitlines()[-1])


class TestImportDependencyClosure(unittest.TestCase):
    def test_bare_import_loads_only_declared_distributions(self) -> None:
        declared = _declared_distributions()
        allowed = set(_RUNTIME_ARTEFACTS)
        for module, dists in packages_distributions().items():
            if any(d.lower().replace("_", "-") in declared for d in dists):
                allowed.add(module)
        for dist, modules in _DISTRIBUTION_IMPORT_ALIASES.items():
            if dist in declared:
                allowed |= modules

        loaded = set(_modules_imported())
        undeclared = sorted(loaded - allowed)

        assert not undeclared, (
            f"`import pirn_agents` loaded third-party modules outside its declared "
            f"dependency closure: {undeclared}. Either declare the distribution in "
            f"pirn-agents' pyproject, or make the import lazy so a clean install "
            f"does not pay for a feature it did not ask for."
        )

    def test_numpy_is_inside_the_closure_via_pirn_core(self) -> None:
        # PIR-780 reported numpy as an *undeclared* dependency reached through
        # `retrieval.vector_stores.in_memory_vector_store`, working "only
        # because it arrives transitively in dev environments". It is in fact
        # declared — pirn-core requires `numpy>=2.4.4` and pirn-agents requires
        # pirn-core — so it is guaranteed by resolution, exactly like `yaml`,
        # which that report already accepted as honest. Pinned so the claim is
        # not re-derived from the absence of numpy in *this* package's
        # pyproject.
        assert "pirn-core" in _declared_distributions()
        assert "numpy" in _declared_distributions()

    def test_the_probe_actually_observes_imports(self) -> None:
        # Guards the check itself: a probe that silently returned nothing would
        # make the assertion above vacuous forever.
        modules = _modules_imported()
        assert "pirn" in modules, modules
        assert len(modules) > 3, modules

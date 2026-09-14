"""Registry-visibility acceptance test for pirn-oilgas (PIR-856).

``pirn_oilgas/__init__.py`` calls ``Registry.fill_registry`` at import time and
now logs — rather than silently swallowing — every module sweet_tea skips
because an optional dependency is missing. This test asserts the other half of
that contract: when every module in the package tree *does* import cleanly
(all extras present), the registry actually holds every ``Knot`` subclass
shipped in the package. If any module fails to import here, the environment is
missing an extra, and the test is skipped rather than failed — this checks
registry completeness in the all-extras-installed case, not that extras are
installed everywhere.
"""

from __future__ import annotations

import importlib
import pkgutil

import pytest
from pirn.core.knot import Knot
from sweet_tea.registry import Registry

import pirn_oilgas


def _walk_knot_subclasses(package: object) -> tuple[set[str], list[str]]:
    """Import every submodule of *package* and collect ``Knot`` subclass names.

    Returns a pair of (fully-qualified ``Knot`` subclass names defined in the
    package, dotted names of submodules that failed to import).

    Identity is keyed by the class's own ``__module__.__qualname__``, not by
    whatever module-level attribute name it happens to be bound to, so a class
    reachable under a second name is still counted once.
    """
    found: set[str] = set()
    failed: list[str] = []
    prefix = package.__name__ + "."
    for _, module_name, _ in pkgutil.walk_packages(package.__path__, prefix):
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            failed.append(module_name)
            continue
        for _name, obj in vars(module).items():
            if isinstance(obj, type) and obj.__module__ == module_name and issubclass(obj, Knot):
                found.add(f"{obj.__module__}.{obj.__qualname__}")
    return found, failed


def test_registry_holds_every_knot_subclass_when_extras_present() -> None:
    found, failed = _walk_knot_subclasses(pirn_oilgas)
    if failed:
        pytest.skip(
            "an optional dependency is missing for: "
            + ", ".join(sorted(failed))
            + " — install pirn-oilgas[oilgas] to run this test"
        )

    registered = {
        f"{entry.class_def.__module__}.{entry.class_def.__qualname__}"
        for entry in Registry.typed_entries(Knot)
        if entry.class_def.__module__.startswith("pirn_oilgas.")
    }

    missing = found - registered
    assert not missing, (
        "Knot subclasses present in the package tree but absent from the "
        f"registry (silently dropped by fill_registry): {sorted(missing)}"
    )

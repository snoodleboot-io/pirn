"""Clean-env install-isolation gate (SCD-25 / ADR-1 constraints C2, C4).

Run this **inside the freshly-created virtualenv** that has exactly one
``pirn-<x>`` installed (plus whatever it pulls transitively):

    <venv>/bin/python scripts/check_install_isolation.py --package pirn-signal

It asserts the *resolved* set of ``pirn-*`` distributions equals the declared
dependency closure for that package — i.e. installing a domain pulls
``pirn-core`` (and ``pirn-data`` for ``pirn-ml``, the one retained domain edge,
ADR-3) and **nothing** from the other domains. This is the per-package
replacement for the monolith's 50+ extras-isolation steps and the runtime
counterpart to the static import-graph gate (``check_import_graph.py``).

For ``pirn-core`` it additionally asserts the no-backend-at-import property:
a bare ``import pirn`` must not import any heavy backend package (C2).

Exit status is non-zero on the first violation, with a human-readable reason.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import pkgutil
import sys

# Declared dependency closure per package: the COMPLETE set of `pirn-*`
# distributions that may be present after `pip install pirn-<x>`. Any pirn-*
# distribution outside this set is an isolation breach (a domain leaked a
# sibling-domain dependency). Mirrors the pyproject `dependencies` floors and
# the C3 sole domain->domain edge (`pirn-ml -> pirn-data`).
_EXPECTED_PIRN_CLOSURE: dict[str, set[str]] = {
    "pirn-core": {"pirn-core"},
    "pirn-signal": {"pirn-core", "pirn-signal"},
    "pirn-data": {"pirn-core", "pirn-data"},
    "pirn-ml": {"pirn-core", "pirn-data", "pirn-ml"},
    "pirn-agents": {"pirn-core", "pirn-agents"},
    "pirn-health": {"pirn-core", "pirn-health"},
    "pirn-oilgas": {"pirn-core", "pirn-oilgas"},
}

# Top-level import name for each distribution (core imports as `pirn`).
_IMPORT_NAME: dict[str, str] = {
    "pirn-core": "pirn",
    "pirn-signal": "pirn_signal",
    "pirn-data": "pirn_data",
    "pirn-ml": "pirn_ml",
    "pirn-agents": "pirn_agents",
    "pirn-health": "pirn_health",
    "pirn-oilgas": "pirn_oilgas",
}

# Heavy backend top-level modules that must NOT be imported by a bare
# `import pirn` (C2 / SCD-07). A representative denylist — importing any one of
# these at core-import time means a backend dependency leaked out of its lazy
# guard. Kept in sync with the connector/domain extras in pirn-core.
_BACKEND_DENYLIST: frozenset[str] = frozenset(
    {
        "asyncpg",
        "aioboto3",
        "boto3",
        "aiokafka",
        "confluent_kafka",
        "zstandard",
        "lz4",
        "snappy",
        "numpy",
        "pandas",
        "scipy",
        "pyarrow",
        "polars",
        "sklearn",
        "torch",
        "tensorflow",
        "h5py",
        "zarr",
        "segyio",
        "nibabel",
        "pydicom",
    }
)


def _installed_pirn_distributions() -> set[str]:
    """Return the normalized names of all installed ``pirn-*`` distributions."""

    names: set[str] = set()
    for dist in importlib.metadata.distributions():
        name = (dist.metadata["Name"] or "").lower().replace("_", "-")
        if name.startswith("pirn-") or name == "pirn":
            names.add(name)
    return names


def _check_closure(package: str) -> list[str]:
    expected = _EXPECTED_PIRN_CLOSURE[package]
    installed = _installed_pirn_distributions()
    violations: list[str] = []

    missing = expected - installed
    if missing:
        violations.append(
            f"{package}: expected pirn distribution(s) not installed: {sorted(missing)}"
        )

    leaked = installed - expected
    if leaked:
        violations.append(
            f"{package}: install-isolation breach — unexpected pirn distribution(s) "
            f"pulled in: {sorted(leaked)} (only {sorted(expected)} are allowed)"
        )
    return violations


def _check_imports(package: str) -> list[str]:
    module = _IMPORT_NAME[package]
    try:
        importlib.import_module(module)
    except Exception as exc:  # noqa: BLE001 — surface any import failure as a gate violation
        return [f"{package}: `import {module}` failed in the clean env: {exc!r}"]
    return []


def _check_no_backend_at_core_import() -> list[str]:
    """Assert a bare ``import pirn`` imported no heavy backend (C2)."""

    importlib.import_module("pirn")
    leaked = sorted(_BACKEND_DENYLIST & set(sys.modules))
    if leaked:
        return [
            "pirn-core: `import pirn` imported backend package(s) that must stay "
            f"lazy: {leaked} (C2 / SCD-07)"
        ]
    return []


def _backend_denylist_for(package: str) -> frozenset[str]:
    """Return the backend top-level modules that must NOT be imported for ``package``.

    ``pirn-core`` uses the broad heavy-backend denylist checked at bare-import
    time (:data:`_BACKEND_DENYLIST`). ``pirn-agents`` ships a small base wheel
    and lazily imports its optional connector backends, so importing *any*
    submodule must not eagerly pull one in — those backend top-level modules are
    forbidden. Packages without a specific entry fall back to the core denylist.
    """
    per_package: dict[str, frozenset[str]] = {
        "pirn-agents": frozenset(
            {
                "httpx",
                "openai",
                "anthropic",
                "qdrant_client",
                "mcp",
                "sentence_transformers",
                "asyncpg",
                "pgvector",
                "chromadb",
                "neo4j",
                "kuzu",
                "aiosqlite",
                "aioboto3",
                "boto3",
                "opentelemetry",
                "outlines",
            }
        ),
    }
    return per_package.get(package, _BACKEND_DENYLIST)


def _check_no_backend_after_submodule_walk(import_name: str, denylist: frozenset[str]) -> list[str]:
    """Import every submodule of ``import_name`` and assert no backend leaked.

    Imports the top-level package, then uses :func:`pkgutil.walk_packages` to
    import EVERY submodule in its tree. Each import is guarded; a submodule that
    fails to import is reported as a violation (rather than skipped) so real
    breakage — including a backend that is eagerly (not lazily) imported and thus
    unresolvable in the clean base env — surfaces. Finally asserts that none of
    ``denylist`` ended up in :data:`sys.modules`, i.e. no submodule eagerly
    imported a backend that is meant to stay behind a lazy guard.
    """

    violations: list[str] = []
    try:
        top = importlib.import_module(import_name)
    except Exception as exc:  # noqa: BLE001 — surface any import failure as a gate violation
        return [f"{import_name}: `import {import_name}` failed in the clean env: {exc!r}"]

    paths = getattr(top, "__path__", None)
    if paths is not None:

        def _onerror(name: str) -> None:
            violations.append(
                f"{import_name}: `import {name}` failed during submodule walk: "
                f"{sys.exc_info()[1]!r}"
            )

        for mod in pkgutil.walk_packages(paths, prefix=f"{import_name}.", onerror=_onerror):
            try:
                importlib.import_module(mod.name)
            except Exception as exc:  # noqa: BLE001 — real breakage must surface, not be hidden
                violations.append(
                    f"{import_name}: `import {mod.name}` failed during submodule walk: {exc!r}"
                )

    leaked = sorted(denylist & set(sys.modules))
    if leaked:
        violations.append(
            f"{import_name}: importing the full submodule tree pulled in backend "
            f"package(s) that must stay lazy: {leaked} (C2 / SCD-07)"
        )
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--package",
        required=True,
        choices=sorted(_EXPECTED_PIRN_CLOSURE),
        help="the single pirn-<x> distribution installed in this clean env",
    )
    args = parser.parse_args()
    package: str = args.package

    violations = _check_closure(package)
    import_violations = _check_imports(package)
    violations += import_violations
    # The no-backend check imports `pirn`; only meaningful if the import worked.
    if package == "pirn-core" and not import_violations:
        violations += _check_no_backend_at_core_import()
    # pirn-agents additionally walks its full submodule tree and asserts no
    # optional connector backend leaks out of its lazy guard (C2). Additive:
    # pirn-core and the other domains keep their existing behavior unchanged.
    if package == "pirn-agents" and not import_violations:
        violations += _check_no_backend_after_submodule_walk(
            _IMPORT_NAME[package], _backend_denylist_for(package)
        )

    if violations:
        print(f"install-isolation gate FAILED for {package}:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    expected = sorted(_EXPECTED_PIRN_CLOSURE[package])
    print(f"install-isolation gate OK for {package}: resolved pirn closure = {expected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

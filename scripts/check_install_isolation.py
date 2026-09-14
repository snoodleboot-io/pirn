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

For every package it then imports the package and EVERY submodule in its
tree (``import <pkg>`` already does this through the sweet_tea registry fill)
and asserts two things (C2 / SCD-07):

* every submodule imports in the clean env — a module that imports an
  optional backend at module scope cannot, so it is reported;
* no backend on the package's denylist ended up in ``sys.modules``. The
  denylist is :data:`_BACKEND_DENYLIST` minus the import names of the
  package's hard-dependency closure (read from the installed distribution
  metadata, so pirn-core's own hard dependencies such as numpy count as hard
  for every package).

Exit status is non-zero on the first violation, with a human-readable reason.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import pkgutil
import re
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

# Top-level import names of the optional backends behind the packages' extras
# (C2 / SCD-07). Importing a package and its whole submodule tree must not import
# any of these unless it is a hard dependency of that package; importing one
# means a backend leaked out of its lazy guard. Kept in sync with the extras in
# every package's pyproject.toml.
_BACKEND_DENYLIST: frozenset[str] = frozenset(
    {
        # pirn-core connector / backend extras
        "aioboto3",
        "aiokafka",
        "asyncpg",
        "boto3",
        "confluent_kafka",
        "h5py",
        "lz4",
        "numpy",
        "snappy",
        "zarr",
        "zstandard",
        # pirn-agents extras
        "aiosqlite",
        "anthropic",
        "bs4",
        "chromadb",
        "docx",
        "httpx",
        "kuzu",
        "mcp",
        "neo4j",
        "openai",
        "opentelemetry",
        "outlines",
        "pgvector",
        "pypdf",
        "qdrant_client",
        "ragas",
        "sentence_transformers",
        # pirn-data extras
        "awkward",
        "dask",
        "datafusion",
        "deltalake",
        "duckdb",
        "eland",
        "great_expectations",
        "ibis",
        "lance",
        "modin",
        "pandas",
        "pandera",
        "polars",
        "pyarrow",
        "pyiceberg",
        "pyspark",
        "ray",
        "tiktoken",
        "xarray",
        # pirn-health extras
        "SimpleITK",
        "dipy",
        "mne",
        "nibabel",
        "pydicom",
        "pyfaidx",
        "pysam",
        # pirn-ml extras
        "joblib",
        "sklearn",
        "tensorflow",
        "torch",
        # pirn-oilgas extras
        "lasio",
        "resfo",
        "segyio",
        # pirn-signal extras
        "PyEMD",
        "librosa",
        "pywt",
        "scipy",
        "soundfile",
        "vmdpy",
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


def _check_versions(package: str, expected_version: str) -> list[str]:
    """Assert every pirn distribution in the closure is the build under test.

    CI installs this build's wheels; a same-named release resolved from the
    public index instead (PR #368: ``pirn-oilgas==0.10.0`` over the wheelhouse's
    ``0.9.0``) would make every later check test the wrong code, so this runs
    before the import and the submodule walk.
    """

    violations: list[str] = []
    for distribution in sorted(_EXPECTED_PIRN_CLOSURE[package]):
        try:
            installed = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            violations.append(f"{package}: {distribution} is not installed")
            continue
        if installed != expected_version:
            violations.append(
                f"{package}: {distribution}=={installed} is installed, but the build under "
                f"test is {expected_version} — the gate would check a different release"
            )
    return violations


def _check_imports(package: str) -> list[str]:
    module = _IMPORT_NAME[package]
    try:
        importlib.import_module(module)
    except Exception as exc:  # noqa: BLE001 — surface any import failure as a gate violation
        return [f"{package}: `import {module}` failed in the clean env: {exc!r}"]
    return []


def _hard_dependency_closure(distribution: str) -> set[str]:
    """Normalized names of ``distribution`` and every hard (non-extra) dependency, transitively."""

    seen: set[str] = set()
    stack = [distribution]
    while stack:
        name = stack.pop()
        key = re.sub(r"[-_.]+", "-", name).lower()
        if key in seen:
            continue
        seen.add(key)
        try:
            requirements = importlib.metadata.requires(name) or []
        except importlib.metadata.PackageNotFoundError:
            continue
        for requirement in requirements:
            if re.search(r"\bextra\s*==", requirement):
                continue
            match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", requirement)
            if match is not None:
                stack.append(match.group(1))
    return seen


def _backend_denylist_for(package: str) -> frozenset[str]:
    """Backend top-level modules that must NOT be imported for ``package``.

    :data:`_BACKEND_DENYLIST` minus the top-level import names provided by the
    package's installed hard-dependency closure — so ``numpy``, a pirn-core
    hard dependency, is allowed for every package, and a backend a package
    declares as a hard dependency is allowed for that package.
    """
    closure = _hard_dependency_closure(package)
    provided = {
        top
        for top, distributions in importlib.metadata.packages_distributions().items()
        if any(re.sub(r"[-_.]+", "-", d).lower() in closure for d in distributions)
    }
    return _BACKEND_DENYLIST - provided


def _check_no_backend_after_submodule_walk(import_name: str, denylist: frozenset[str]) -> list[str]:
    """Import every submodule of ``import_name`` and assert no backend leaked.

    Imports the top-level package, then uses :func:`pkgutil.walk_packages` to
    import EVERY submodule in its tree (what ``import <pkg>``'s registry fill
    does, minus its skip-on-ImportError leniency). Each import is guarded; a submodule that
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
    parser.add_argument(
        "--expect-version",
        required=True,
        help="the version of the build under test; every installed pirn-* closure "
        "distribution must report exactly this version",
    )
    args = parser.parse_args()
    package: str = args.package

    violations = _check_closure(package)
    version_violations = _check_versions(package, args.expect_version)
    if version_violations:
        print(f"install-isolation gate FAILED for {package}:", file=sys.stderr)
        for v in [*violations, *version_violations]:
            print(f"  - {v}", file=sys.stderr)
        return 1
    import_violations = _check_imports(package)
    violations += import_violations
    # Every package walks its full submodule tree and asserts no optional
    # backend leaks out of its lazy guard (C2); only meaningful if the import worked.
    if not import_violations:
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

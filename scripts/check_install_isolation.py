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
  denylist is **derived from the packages' declared extras**
  (:class:`gatekit.extras_backend_denylist.ExtrasBackendDenylist`) minus the
  import names of the package's hard-dependency closure (read from the installed
  distribution metadata, so pirn-core's own hard dependencies such as numpy count
  as hard for every package). It used to be hand-written, and had drifted ~95
  distributions behind the extras actually declared.

Exit status
-----------
* ``0`` — the closure, versions, imports and submodule walk are all clean.
* ``1`` — violations, listed on stderr.
* ``2`` — the gate could not be built: no workspace packages to read extras
  from, or a declared distribution whose top-level import name cannot be
  resolved. Such a name must fail loudly; dropping it silently shrinks the
  denylist, which is the drift this gate now derives its way out of.
"""

from __future__ import annotations

import argparse
import functools
import importlib
import importlib.metadata
import pkgutil
import re
import sys
import tomllib
from pathlib import Path
from typing import ClassVar

from gatekit.extras_backend_denylist import ExtrasBackendDenylist


class CheckInstallIsolation:
    """Assert a clean single-package install resolves and imports in isolation."""

    # Declared dependency closure per package: the COMPLETE set of `pirn-*`
    # distributions that may be present after `pip install pirn-<x>`. Any pirn-*
    # distribution outside this set is an isolation breach (a domain leaked a
    # sibling-domain dependency). Mirrors the pyproject `dependencies` floors and
    # the C3 sole domain->domain edge (`pirn-ml -> pirn-data`).
    _expected_pirn_closure: ClassVar[dict[str, set[str]]] = {
        "pirn-core": {"pirn-core"},
        "pirn-signal": {"pirn-core", "pirn-signal"},
        "pirn-data": {"pirn-core", "pirn-data"},
        "pirn-ml": {"pirn-core", "pirn-data", "pirn-ml"},
        "pirn-agents": {"pirn-core", "pirn-agents"},
        "pirn-health": {"pirn-core", "pirn-health"},
        "pirn-oilgas": {"pirn-core", "pirn-oilgas"},
    }

    # Top-level import name for each distribution (core imports as `pirn`).
    _import_names: ClassVar[dict[str, str]] = {
        "pirn-core": "pirn",
        "pirn-signal": "pirn_signal",
        "pirn-data": "pirn_data",
        "pirn-ml": "pirn_ml",
        "pirn-agents": "pirn_agents",
        "pirn-health": "pirn_health",
        "pirn-oilgas": "pirn_oilgas",
    }

    _repo_root: ClassVar[Path] = Path(__file__).resolve().parent.parent

    @staticmethod
    def backend_denylist() -> frozenset[str]:
        """Optional-backend modules derived from every package's declared extras."""
        return ExtrasBackendDenylist.derive(CheckInstallIsolation._repo_root / "packages")

    @staticmethod
    def _installed_pirn_distributions() -> set[str]:
        """Return the normalized names of all installed ``pirn-*`` distributions."""
        names: set[str] = set()
        for dist in importlib.metadata.distributions():
            name = (dist.metadata["Name"] or "").lower().replace("_", "-")
            if name.startswith("pirn-") or name == "pirn":
                names.add(name)
        return names

    @staticmethod
    def _check_closure(package: str) -> list[str]:
        expected = CheckInstallIsolation._expected_pirn_closure[package]
        installed = CheckInstallIsolation._installed_pirn_distributions()
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

    @staticmethod
    def _check_versions(package: str, expected_version: str) -> list[str]:
        """Assert every pirn distribution in the closure is the build under test.

        CI installs this build's wheels; a same-named release resolved from the
        public index instead (PR #368: ``pirn-oilgas==0.10.0`` over the wheelhouse's
        ``0.9.0``) would make every later check test the wrong code, so this runs
        before the import and the submodule walk.
        """
        violations: list[str] = []
        for distribution in sorted(CheckInstallIsolation._expected_pirn_closure[package]):
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

    @staticmethod
    def _check_imports(package: str) -> list[str]:
        module = CheckInstallIsolation._import_names[package]
        try:
            importlib.import_module(module)
        except Exception as exc:
            return [f"{package}: `import {module}` failed in the clean env: {exc!r}"]
        return []

    @staticmethod
    def _workspace_requirements(distribution: str) -> list[str]:
        """Hard requirements of a pirn workspace package read from its ``pyproject.toml``.

        Returns an empty list for a name that is not a workspace package.
        """
        pyproject = CheckInstallIsolation._repo_root / "packages" / distribution / "pyproject.toml"
        if not distribution.startswith("pirn-") or not pyproject.is_file():
            return []
        with pyproject.open("rb") as handle:
            project = tomllib.load(handle).get("project", {})
        dependencies = project.get("dependencies", [])
        return [str(requirement) for requirement in dependencies]

    @staticmethod
    def _hard_dependency_closure(distribution: str) -> set[str]:
        """Normalized names of ``distribution`` and every hard dependency, transitively."""
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
                # A pirn workspace package that is not installed in this environment
                # (e.g. a per-package CI job) still has a known hard-dependency set:
                # read it from its pyproject so the denylist does not depend on which
                # pirn wheels happen to be installed.
                requirements = CheckInstallIsolation._workspace_requirements(key)
            for requirement in requirements:
                if re.search(r"\bextra\s*==", requirement):
                    continue
                match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", requirement)
                if match is not None:
                    stack.append(match.group(1))
        return seen

    @staticmethod
    def _backend_denylist_for(package: str) -> frozenset[str]:
        """Backend top-level modules that must NOT be imported for ``package``.

        The derived extras denylist minus the top-level import names provided by
        the package's installed hard-dependency closure — so ``numpy``, a
        pirn-core hard dependency, is allowed for every package, and a backend a
        package declares as a hard dependency is allowed for that package.
        """
        closure = CheckInstallIsolation._hard_dependency_closure(package)
        provided = {
            top
            for top, distributions in importlib.metadata.packages_distributions().items()
            if any(re.sub(r"[-_.]+", "-", d).lower() in closure for d in distributions)
        }
        return CheckInstallIsolation.backend_denylist() - provided

    @staticmethod
    def _record_walk_error(import_name: str, violations: list[str], name: str) -> None:
        """``pkgutil.walk_packages`` error callback — a failed walk is a violation."""
        violations.append(
            f"{import_name}: `import {name}` failed during submodule walk: {sys.exc_info()[1]!r}"
        )

    @staticmethod
    def _check_no_backend_after_submodule_walk(
        import_name: str, denylist: frozenset[str]
    ) -> list[str]:
        """Import every submodule of ``import_name`` and assert no backend leaked.

        Imports the top-level package, then uses :func:`pkgutil.walk_packages` to
        import EVERY submodule in its tree (what ``import <pkg>``'s registry fill
        does, minus its skip-on-ImportError leniency). Each import is guarded; a
        submodule that fails to import is reported as a violation (rather than
        skipped) so real breakage — including a backend that is eagerly (not lazily)
        imported and thus unresolvable in the clean base env — surfaces. Finally
        asserts that none of ``denylist`` ended up in :data:`sys.modules`, i.e. no
        submodule eagerly imported a backend meant to stay behind a lazy guard.
        """
        violations: list[str] = []
        try:
            top = importlib.import_module(import_name)
        except Exception as exc:
            return [f"{import_name}: `import {import_name}` failed in the clean env: {exc!r}"]

        paths = getattr(top, "__path__", None)
        if paths is not None:
            onerror = functools.partial(
                CheckInstallIsolation._record_walk_error, import_name, violations
            )
            for mod in pkgutil.walk_packages(paths, prefix=f"{import_name}.", onerror=onerror):
                try:
                    importlib.import_module(mod.name)
                except Exception as exc:
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

    @staticmethod
    def main(argv: list[str] | None = None) -> int:
        """Run the install-isolation gate for one package; return the exit code."""
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument(
            "--package",
            required=True,
            choices=sorted(CheckInstallIsolation._expected_pirn_closure),
            help="the single pirn-<x> distribution installed in this clean env",
        )
        parser.add_argument(
            "--expect-version",
            required=True,
            help="the version of the build under test; every installed pirn-* closure "
            "distribution must report exactly this version",
        )
        args = parser.parse_args(argv)
        package: str = args.package

        violations = CheckInstallIsolation._check_closure(package)
        version_violations = CheckInstallIsolation._check_versions(package, args.expect_version)
        if version_violations:
            print(f"install-isolation gate FAILED for {package}:", file=sys.stderr)
            for violation in [*violations, *version_violations]:
                print(f"  - {violation}", file=sys.stderr)
            return 1
        import_violations = CheckInstallIsolation._check_imports(package)
        violations += import_violations
        # Every package walks its full submodule tree and asserts no optional
        # backend leaks out of its lazy guard (C2); only meaningful if the import worked.
        if not import_violations:
            try:
                denylist = CheckInstallIsolation._backend_denylist_for(package)
            except ValueError as error:
                print(f"install-isolation gate could not run: {error}", file=sys.stderr)
                return 2
            violations += CheckInstallIsolation._check_no_backend_after_submodule_walk(
                CheckInstallIsolation._import_names[package], denylist
            )

        if violations:
            print(f"install-isolation gate FAILED for {package}:", file=sys.stderr)
            for violation in violations:
                print(f"  - {violation}", file=sys.stderr)
            return 1

        expected = sorted(CheckInstallIsolation._expected_pirn_closure[package])
        print(f"install-isolation gate OK for {package}: resolved pirn closure = {expected}")
        return 0


if __name__ == "__main__":
    raise SystemExit(CheckInstallIsolation.main())

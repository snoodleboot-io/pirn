"""Lockstep version stamping + C4 floor gate for the workspace (SCD-27 / ADR-6).

All eight workspace packages release in **lockstep**: one version bump stamps
every `pyproject.toml` identically, and every inter-package dependency pins the
same floor with a compatible upper bound (constraint C4). This script is both
the stamper and the gate:

    # stamp every package + every inter-package pin to a new lockstep version
    python scripts/stamp_workspace_version.py --version 0.5.0

    # CI gate: assert lockstep holds (all versions equal, all pins floored/capped)
    python scripts/stamp_workspace_version.py --check

Upper bound follows ADR-6: while MAJOR is 0 the MINOR acts as the breaking axis
(`0.4.0` → `<0.5.0`); from 1.0 onward it is the next MAJOR (`1.2.0` → `<2.0.0`).
Edits are surgical regex replacements so the pyproject comments/formatting are
preserved.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import ClassVar


class StampWorkspaceVersion:
    """Stamp — and gate — the lockstep version across every workspace package."""

    # The seven workspace distributions (core + six domains). The plan's "eight"
    # counts a future `pirn` all-domains meta-distribution; until that ships, the
    # all-domains convenience is core's `[all-domains]` extra, whose pins are
    # stamped here too.
    _packages: ClassVar[tuple[str, ...]] = (
        "pirn-core",
        "pirn-signal",
        "pirn-data",
        "pirn-ml",
        "pirn-agents",
        "pirn-health",
        "pirn-oilgas",
    )

    _version_re: ClassVar[re.Pattern[str]] = re.compile(
        r'^(?P<pre>version\s*=\s*")(?P<ver>[^"]+)(?P<post>")', re.MULTILINE
    )
    _pin_re: ClassVar[re.Pattern[str]] = re.compile(
        r'"(?P<dist>' + "|".join(_packages) + r')>=(?P<floor>[^,"]+),<(?P<cap>[^"]+)"'
    )
    _semver_re: ClassVar[re.Pattern[str]] = re.compile(r"^(\d+)\.(\d+)\.(\d+)")

    @staticmethod
    def _upper_bound(version: str) -> str:
        """ADR-6 compatible cap: next-minor while 0.x, else next-major."""
        match = StampWorkspaceVersion._semver_re.match(version)
        if not match:
            raise ValueError(f"not a MAJOR.MINOR.PATCH version: {version!r}")
        major, minor, _ = (int(group) for group in match.groups())
        return f"0.{minor + 1}.0" if major == 0 else f"{major + 1}.0.0"

    @staticmethod
    def _pyproject_paths() -> list[Path]:
        return [
            Path("packages") / pkg / "pyproject.toml" for pkg in StampWorkspaceVersion._packages
        ]

    @staticmethod
    def _stamp_text(text: str, version: str, cap: str) -> str:
        text = StampWorkspaceVersion._version_re.sub(rf"\g<pre>{version}\g<post>", text, count=1)
        return StampWorkspaceVersion._pin_re.sub(rf'"\g<dist>>={version},<{cap}"', text)

    @staticmethod
    def stamp(version: str) -> None:
        """Rewrite every package pyproject to *version* with an ADR-6 cap."""
        cap = StampWorkspaceVersion._upper_bound(version)
        for path in StampWorkspaceVersion._pyproject_paths():
            original = path.read_text(encoding="utf-8")
            updated = StampWorkspaceVersion._stamp_text(original, version, cap)
            if updated != original:
                path.write_text(updated, encoding="utf-8")
                print(f"stamped {path} -> {version} (pins <{cap})")
            else:
                print(f"unchanged {path}")

    @staticmethod
    def check(expected: str | None) -> list[str]:
        """Assert lockstep + C4: equal versions and floored/capped pins everywhere."""
        violations: list[str] = []
        versions: dict[str, str] = {}
        for path in StampWorkspaceVersion._pyproject_paths():
            text = path.read_text(encoding="utf-8")
            match = StampWorkspaceVersion._version_re.search(text)
            if not match:
                violations.append(f"{path}: no top-level version field")
                continue
            versions[path.parent.name] = match.group("ver")

        if not versions:
            return ["no package versions found"]

        target = expected or sorted(versions.values())[-1]
        cap = StampWorkspaceVersion._upper_bound(target)

        # C4-a: every package stamped to the same lockstep version.
        for pkg, version in versions.items():
            if version != target:
                violations.append(f"{pkg}: version {version} != lockstep target {target}")

        # C4-b: every inter-package pin floors at the target and caps at `cap`.
        for path in StampWorkspaceVersion._pyproject_paths():
            for pin in StampWorkspaceVersion._pin_re.finditer(path.read_text(encoding="utf-8")):
                if pin.group("floor") != target or pin.group("cap") != cap:
                    violations.append(
                        f"{path}: pin {pin.group(0)} must be "
                        f'">={target},<{cap}" (C4 lockstep floor, ADR-6)'
                    )
        return violations

    @staticmethod
    def main() -> int:
        """Stamp (``--version``) or gate (``--check``); return the process exit code."""
        parser = argparse.ArgumentParser(description=__doc__)
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--version", help="lockstep version to stamp (e.g. 0.5.0)")
        group.add_argument(
            "--check",
            action="store_true",
            help="assert lockstep + C4 floors without writing (CI gate)",
        )
        parser.add_argument(
            "--expected",
            help="in --check mode, the version to assert (default: the max found)",
        )
        args = parser.parse_args()

        if args.version:
            StampWorkspaceVersion.stamp(args.version)
            # Self-verify the stamp is internally consistent.
            violations = StampWorkspaceVersion.check(args.version)
            if violations:
                print("stamp produced an inconsistent state:", file=sys.stderr)
                for violation in violations:
                    print(f"  - {violation}", file=sys.stderr)
                return 1
            print(f"lockstep stamp OK: all packages at {args.version}")
            return 0

        violations = StampWorkspaceVersion.check(args.expected)
        if violations:
            print("lockstep / C4 gate FAILED:", file=sys.stderr)
            for violation in violations:
                print(f"  - {violation}", file=sys.stderr)
            return 1
        print("lockstep / C4 gate OK: all packages + pins consistent")
        return 0


if __name__ == "__main__":
    raise SystemExit(StampWorkspaceVersion.main())

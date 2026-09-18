"""``ConventionScan`` — collect the files, resolve the hierarchy, run every checker."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from gatekit.alias_checker import AliasChecker
from gatekit.class_hierarchy_index import ClassHierarchyIndex
from gatekit.deprecation_checker import DeprecationChecker
from gatekit.knot_design_checker import KnotDesignChecker
from gatekit.module_shape_checker import ModuleShapeChecker
from gatekit.scan_target import ScanTarget
from gatekit.source_file import SourceFile
from gatekit.suppression_checker import SuppressionChecker
from gatekit.suppression_rule_catalog import SuppressionRuleCatalog
from gatekit.violation import Violation


class ConventionScan:
    """One pass of the convention gate over a set of paths."""

    _skip_dir_names: ClassVar[frozenset[str]] = frozenset(
        {
            ".git",
            ".ruff_cache",
            ".tox",
            ".venv",
            "__pycache__",
            "build",
            "dist",
            "node_modules",
            "site",
            "typings",
            "venv",
        }
    )
    # Rules about a module's own layout, and about the design of a Knot. Both
    # families are enforced everywhere except test code; see ``CheckConventions``'
    # module docstring for why that boundary exists and what would move it.
    structural_rules: ClassVar[frozenset[str]] = frozenset(
        {
            "filename_mismatch",
            "module_level_constant",
            "module_level_function",
            "multi_class_file",
            "nested_def_missing_override",
            "reexport_module",
        }
    )
    knot_design_rules: ClassVar[frozenset[str]] = frozenset(
        {
            "gate_wrong_base",
            "knot_init_impure",
            "knot_process_kwargs_name",
            "knot_property",
            "knot_self_assignment",
            "knot_super_init_argument",
        }
    )
    rules: ClassVar[tuple[str, ...]] = (
        "multi_class_file",
        "module_level_function",
        "nested_def_missing_override",
        "filename_mismatch",
        "module_level_constant",
        "reexport_module",
        "gate_wrong_base",
        "knot_init_impure",
        "knot_super_init_argument",
        "knot_self_assignment",
        "knot_property",
        "knot_process_kwargs_name",
        "deprecation_reference",
        "module_alias_assignment",
        "class_alias_assignment",
        "payload_alias_property",
        "suppression_without_rule_or_reason",
        "suppression_unknown_rule",
        "file_level_directive",
        "unparsable_file",
    )

    def __init__(self, repository_root: Path, catalog: SuppressionRuleCatalog) -> None:
        self._repository_root = repository_root.resolve()
        self._index = ClassHierarchyIndex()
        self._knots = KnotDesignChecker(self._index)
        self._aliases = AliasChecker(self._index, self._knots)
        self._shapes = ModuleShapeChecker()
        self._deprecation = DeprecationChecker()
        self._suppressions = SuppressionChecker(catalog)
        self._parsed: dict[Path, SourceFile] = {}
        self._checked: set[Path] = set()
        self._unparsable: dict[Path, Violation] = {}

    # -- collecting ----------------------------------------------------------

    def add_paths(self, paths: list[Path], *, checked: bool) -> None:
        """Index every ``.py`` file under ``paths``; ``checked`` files are also reported on."""
        for path in paths:
            for candidate in self._python_files(path):
                self._add_file(candidate, checked=checked)

    @classmethod
    def _python_files(cls, path: Path) -> list[Path]:
        if path.is_file():
            return [path] if path.suffix == ".py" else []
        return [
            candidate
            for candidate in sorted(path.rglob("*.py"))
            if not any(part in cls._skip_dir_names for part in candidate.parts)
        ]

    def _add_file(self, path: Path, *, checked: bool) -> None:
        resolved = path.resolve()
        if checked:
            self._checked.add(resolved)
        if resolved in self._parsed or resolved in self._unparsable:
            return
        source_file = SourceFile(path)
        if source_file.parse_error is not None:
            self._unparsable[resolved] = Violation(
                "unparsable_file", path, 1, source_file.parse_error
            )
            return
        self._parsed[resolved] = source_file
        self._index.add_file(source_file)

    def targets(self) -> list[ScanTarget]:
        return [
            ScanTarget(source_file, self._repository_root)
            for path, source_file in sorted(self._parsed.items())
            if path in self._checked
        ]

    @property
    def checked_file_count(self) -> int:
        return len(self._checked)

    # -- running -------------------------------------------------------------

    def run(self) -> list[Violation]:
        violations = [
            violation for path, violation in self._unparsable.items() if path in self._checked
        ]
        for target in self.targets():
            violations.extend(self.check_target(target))
        violations.sort(key=lambda violation: (str(violation.path), violation.lineno))
        return violations

    def check_target(self, target: ScanTarget) -> list[Violation]:
        source_file = target.source_file
        found = [
            *self._shapes.check(source_file),
            *self._knots.check(source_file),
            *self._aliases.check(source_file),
            *self._deprecation.check(source_file),
            *self._suppressions.check(source_file),
        ]
        if not target.is_test_code:
            return found
        deferred = self.structural_rules | self.knot_design_rules
        return [violation for violation in found if violation.rule not in deferred]

    def counts(self, violations: list[Violation]) -> dict[str, dict[str, int]]:
        """Per-package, per-rule counts over the packages this scan actually checked."""
        targets = self.targets()
        package_of = {str(target.path.resolve()): target.package for target in targets}
        counts: dict[str, dict[str, int]] = {}
        for target in targets:
            counts.setdefault(target.package, dict.fromkeys(self.rules, 0))
        for violation in violations:
            package = package_of.get(str(violation.path.resolve()), "?")
            rule_counts = counts.setdefault(package, dict.fromkeys(self.rules, 0))
            rule_counts[violation.rule] = rule_counts.get(violation.rule, 0) + 1
        return counts

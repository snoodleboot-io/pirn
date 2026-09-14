"""Every optional import in pirn_agents names this package and one of its real extras.

pirn_agents imports its optional backends through
:meth:`pirn.core.optional_dependency.OptionalDependency.require`. The install hint
that call raises is only useful if it names ``pirn-agents`` and an extra that
``pyproject.toml`` actually declares, so this test reads every call site.
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

import pytest
from pirn.core.optional_dependency import OptionalDependency

import pirn_agents


class TestOptionalDependencyCallSites:
    @staticmethod
    def _declared_extras() -> set[str]:
        pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
        project = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]
        return set(project.get("optional-dependencies", {}))

    @staticmethod
    def _require_calls() -> list[tuple[str, ast.Call]]:
        calls: list[tuple[str, ast.Call]] = []
        for package_dir in pirn_agents.__path__:
            for source in sorted(Path(package_dir).rglob("*.py")):
                tree = ast.parse(source.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "require"
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "OptionalDependency"
                    ):
                        calls.append((f"{source.name}:{node.lineno}", node))
        return calls

    def test_the_package_has_optional_imports(self) -> None:
        # Arrange / Act
        calls = self._require_calls()

        # Assert
        assert calls

    def test_every_call_names_this_package_and_a_declared_extra(self) -> None:
        # Arrange
        extras = self._declared_extras()

        # Act
        wrong: list[str] = []
        for location, call in self._require_calls():
            keywords = {keyword.arg: keyword.value for keyword in call.keywords}
            package = keywords.get("package")
            extra = keywords.get("extra")
            if not (isinstance(package, ast.Constant) and package.value == "pirn-agents"):
                wrong.append(f"{location}: package is not 'pirn-agents'")
            if not (isinstance(extra, ast.Constant) and extra.value in extras):
                wrong.append(f"{location}: extra is not one of {sorted(extras)}")

        # Assert
        assert wrong == []

    def test_a_missing_module_names_the_package_extra(self) -> None:
        # Arrange
        extra = sorted(self._declared_extras())[0]

        # Act / Assert
        with pytest.raises(ImportError, match=rf'pip install "pirn-agents\[{extra}\]"'):
            OptionalDependency.require(
                "pirn_agents_absent_backend", extra=extra, package="pirn-agents"
            )

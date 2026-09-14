"""Tests for :class:`pirn.core.optional_dependency.OptionalDependency`."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from pirn.core.optional_dependency import OptionalDependency


class TestOptionalDependencyRequire:
    def test_returns_the_imported_module(self) -> None:
        # Arrange / Act
        module = OptionalDependency.require("json", extra="unused")

        # Assert
        assert module is json

    def test_imports_a_dotted_submodule(self) -> None:
        # Arrange / Act
        module = OptionalDependency.require("os.path", extra="unused")

        # Assert
        assert module is sys.modules["os.path"]

    def test_missing_module_names_the_default_core_extra(self) -> None:
        # Arrange / Act
        with pytest.raises(ImportError) as info:
            OptionalDependency.require("nope_missing_xyz", extra="vector")

        # Assert
        message = str(info.value)
        assert "'nope_missing_xyz'" in message
        assert 'pip install "pirn-core[vector]"' in message

    def test_missing_module_names_the_given_package(self) -> None:
        # Arrange / Act
        with pytest.raises(ImportError) as info:
            OptionalDependency.require("nope_missing_xyz", extra="web", package="pirn-agents")

        # Assert
        assert 'pip install "pirn-agents[web]"' in str(info.value)

    def test_missing_module_chains_the_original_error(self) -> None:
        # Arrange / Act
        with pytest.raises(ImportError) as info:
            OptionalDependency.require("nope_missing_xyz", extra="vector")

        # Assert
        assert isinstance(info.value.__cause__, ModuleNotFoundError)

    def test_blocked_module_raises_the_install_hint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Arrange: a ``None`` entry in ``sys.modules`` makes the import fail.
        monkeypatch.setitem(sys.modules, "pirn_blocked_backend_xyz", None)

        # Act
        with pytest.raises(ImportError) as info:
            OptionalDependency.require("pirn_blocked_backend_xyz", extra="blocked")

        # Assert
        assert 'pip install "pirn-core[blocked]"' in str(info.value)

    @pytest.mark.parametrize(
        ("module", "extra", "package", "name"),
        [
            (1, "x", "pirn-core", "module"),
            ("json", None, "pirn-core", "extra"),
            ("json", "x", 3.0, "package"),
        ],
    )
    def test_non_str_argument_raises_type_error(
        self, module: Any, extra: Any, package: Any, name: str
    ) -> None:
        # Arrange / Act / Assert
        with pytest.raises(TypeError, match=f"{name} must be a str"):
            OptionalDependency.require(module, extra=extra, package=package)

    @pytest.mark.parametrize(
        ("module", "extra", "package", "name"),
        [
            ("", "x", "pirn-core", "module"),
            ("json", "", "pirn-core", "extra"),
            ("json", "x", "", "package"),
        ],
    )
    def test_empty_argument_raises_value_error(
        self, module: str, extra: str, package: str, name: str
    ) -> None:
        # Arrange / Act / Assert
        with pytest.raises(ValueError, match=f"{name} must be a non-empty str"):
            OptionalDependency.require(module, extra=extra, package=package)

    def test_import_error_raised_inside_an_installed_module_propagates_unchanged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Arrange: the requested module is installed, but executing it fails on
        # an import of its own -- a broken install, not a missing extra.
        (tmp_path / "pirn_installed_but_broken_xyz.py").write_text(
            "import pirn_its_own_missing_dependency_xyz\n"
        )
        monkeypatch.syspath_prepend(str(tmp_path))

        # Act
        with pytest.raises(ImportError) as info:
            OptionalDependency.require("pirn_installed_but_broken_xyz", extra="broken")

        # Assert: the real failure, never the "install the extra" relabel.
        assert info.value.name == "pirn_its_own_missing_dependency_xyz"
        assert "pip install" not in str(info.value)

    def test_missing_parent_package_of_a_dotted_module_raises_the_install_hint(self) -> None:
        # Arrange / Act
        with pytest.raises(ImportError) as info:
            OptionalDependency.require("nope_missing_xyz.sub.module", extra="deep")

        # Assert
        assert 'pip install "pirn-core[deep]"' in str(info.value)

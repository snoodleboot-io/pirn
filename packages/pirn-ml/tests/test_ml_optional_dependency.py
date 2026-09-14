"""Tests for :class:`MlOptionalDependency`."""

from __future__ import annotations

import json

import pytest

from pirn_ml.ml_optional_dependency import MlOptionalDependency


class TestRequire:
    def test_returns_the_imported_module(self) -> None:
        # Arrange / Act
        module = MlOptionalDependency.require("json", extra="ml")

        # Assert
        assert module is json

    def test_missing_module_names_the_extra(self) -> None:
        # Arrange
        missing = "pirn_ml_definitely_not_installed_module"

        # Act / Assert
        with pytest.raises(ImportError, match=r"pip install pirn-ml\[ml\]") as info:
            MlOptionalDependency.require(missing, extra="ml")
        assert missing in str(info.value)
        assert isinstance(info.value.__cause__, ImportError)

"""Unit tests for :class:`HealthOptionalDependency`."""

from __future__ import annotations

import json
import sys
import unittest
from unittest.mock import patch

from pirn_health.health_optional_dependency import HealthOptionalDependency


class TestRequire(unittest.TestCase):
    def test_returns_the_imported_module(self) -> None:
        module = HealthOptionalDependency.require("json", extra="health")
        assert module is json

    def test_returns_a_dotted_submodule(self) -> None:
        import os.path

        module = HealthOptionalDependency.require("os.path", extra="health")
        assert module is os.path

    def test_missing_module_names_module_and_install_command(self) -> None:
        with patch.dict(sys.modules, {"pirn_health_absent_sdk": None}):
            with self.assertRaises(ImportError) as ctx:
                HealthOptionalDependency.require("pirn_health_absent_sdk", extra="mri")
        message = str(ctx.exception)
        assert "'pirn_health_absent_sdk'" in message
        assert "pip install 'pirn-health[mri]'" in message

    def test_missing_module_chains_the_original_error(self) -> None:
        with patch.dict(sys.modules, {"pirn_health_absent_sdk": None}):
            with self.assertRaises(ImportError) as ctx:
                HealthOptionalDependency.require("pirn_health_absent_sdk", extra="health")
        assert isinstance(ctx.exception.__cause__, ImportError)

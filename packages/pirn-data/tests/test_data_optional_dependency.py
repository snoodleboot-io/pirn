"""Tests for :class:`DataOptionalDependency`."""

from __future__ import annotations

import json
import unittest

from pirn_data.data_optional_dependency import DataOptionalDependency


class TestDataOptionalDependency(unittest.TestCase):
    def test_returns_the_imported_module(self) -> None:
        assert DataOptionalDependency.require("json", extra="data") is json

    def test_missing_module_names_the_extra(self) -> None:
        with self.assertRaisesRegex(ImportError, r'pip install "pirn-data\[delta\]"') as ctx:
            DataOptionalDependency.require("pirn_data_no_such_module", extra="delta")
        assert isinstance(ctx.exception.__cause__, ImportError)

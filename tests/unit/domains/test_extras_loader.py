"""Tests for :class:`ExtrasLoader`."""

from __future__ import annotations

import unittest

from pirn.domains.extras_loader import ExtrasLoader


class TestExtrasLoader(unittest.TestCase):
    def test_extra_name_property(self) -> None:
        loader = ExtrasLoader("myextra", ["os"])
        self.assertEqual(loader.extra_name, "myextra")

    def test_modules_property_returns_tuple(self) -> None:
        loader = ExtrasLoader("x", ["os", "sys"])
        self.assertEqual(loader.modules, ("os", "sys"))

    def test_require_passes_when_modules_installed(self) -> None:
        loader = ExtrasLoader("stdlib", ["os", "sys"])
        loader.require()  # should not raise

    def test_require_raises_import_error_for_missing_module(self) -> None:
        loader = ExtrasLoader("fake", ["_pirn_no_such_module_xyz"])
        with self.assertRaises(ImportError) as ctx:
            loader.require()
        self.assertIn("_pirn_no_such_module_xyz", str(ctx.exception))
        self.assertIn("fake", str(ctx.exception))

    def test_require_message_includes_pip_install_hint(self) -> None:
        loader = ExtrasLoader("mylib", ["_pirn_missing_dep"])
        with self.assertRaises(ImportError) as ctx:
            loader.require()
        self.assertIn("pip install", str(ctx.exception))

    def test_modules_list_is_copied(self) -> None:
        original = ["os"]
        loader = ExtrasLoader("x", original)
        original.append("sys")
        self.assertEqual(loader.modules, ("os",))

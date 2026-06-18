"""Tests for the ``pirn.domains.*`` compatibility shim (SCD-18).

Covers both resolution paths:
- ``import pirn.domains.<x>`` statements via the meta-path finder.
- ``from pirn.domains import <x>`` / attribute access via ``__getattr__``.
"""

from __future__ import annotations

import importlib
import sys
import unittest
import warnings
from unittest.mock import patch

from pirn.domains._domain_compat_finder import DomainCompatFinder


def _purge(*fullnames: str) -> None:
    for name in fullnames:
        sys.modules.pop(name, None)


class TestImportStatement(unittest.TestCase):
    def test_import_binds_to_backing_package(self) -> None:
        import pirn_data

        _purge("pirn.domains.data")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            legacy = importlib.import_module("pirn.domains.data")

        self.assertIs(legacy, pirn_data)
        self.assertIs(sys.modules["pirn.domains.data"], pirn_data)
        self.assertTrue(
            any(issubclass(w.category, DeprecationWarning) for w in caught),
            "expected a DeprecationWarning",
        )

    def test_from_import_statement_binds_to_backing_package(self) -> None:
        import pirn_signal

        _purge("pirn.domains.signal")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from pirn.domains import signal

        self.assertIs(signal, pirn_signal)

    def test_alias_import_binds_to_backing_package(self) -> None:
        import pirn_data

        _purge("pirn.domains.data")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            import pirn.domains.data as aliased

        self.assertIs(aliased, pirn_data)

    def test_submodule_import_resolves(self) -> None:
        import pirn_data.data_schema

        _purge("pirn.domains.data.data_schema")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            legacy_sub = importlib.import_module("pirn.domains.data.data_schema")

        self.assertIs(legacy_sub, pirn_data.data_schema)


class TestAttributeAccess(unittest.TestCase):
    def test_attribute_access_resolves(self) -> None:
        _purge("pirn.domains.ml")
        import pirn.domains

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            module = pirn.domains.ml

            import pirn_ml

        self.assertIs(module, pirn_ml)

    def test_unknown_attribute_raises_attribute_error(self) -> None:
        import pirn.domains

        with self.assertRaises(AttributeError):
            pirn.domains.not_a_domain  # noqa: B018


class TestAbsentPackage(unittest.TestCase):
    def test_import_statement_names_pip_install(self) -> None:
        _purge("pirn.domains.health", "pirn_health")
        with patch.object(
            DomainCompatFinder, "import_legacy", wraps=DomainCompatFinder.import_legacy
        ):
            with patch("pirn.domains._domain_compat_finder.find_spec", return_value=None):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", DeprecationWarning)
                    with self.assertRaises(ImportError) as ctx:
                        importlib.import_module("pirn.domains.health")
        self.assertIn("pip install pirn-health", str(ctx.exception))

    def test_getattr_names_pip_install(self) -> None:
        _purge("pirn.domains.oilgas", "pirn_oilgas")
        import pirn.domains

        with patch("pirn.domains._domain_compat_finder.find_spec", return_value=None):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                with self.assertRaises(ImportError) as ctx:
                    pirn.domains.oilgas  # noqa: B018
        self.assertIn("pip install pirn-oilgas", str(ctx.exception))


class TestFinderRegistration(unittest.TestCase):
    def test_register_is_idempotent(self) -> None:
        before = sum(isinstance(f, DomainCompatFinder) for f in sys.meta_path)
        DomainCompatFinder.register()
        DomainCompatFinder.register()
        after = sum(isinstance(f, DomainCompatFinder) for f in sys.meta_path)
        self.assertEqual(before, after)
        self.assertEqual(after, 1)

    def test_resolve_target_maps_known_domains(self) -> None:
        self.assertEqual(DomainCompatFinder.resolve_target("pirn.domains.data"), "pirn_data")
        self.assertEqual(
            DomainCompatFinder.resolve_target("pirn.domains.data.frames"),
            "pirn_data.frames",
        )

    def test_resolve_target_ignores_non_domains(self) -> None:
        self.assertIsNone(DomainCompatFinder.resolve_target("pirn.domains.bogus"))
        self.assertIsNone(DomainCompatFinder.resolve_target("pirn.connectors"))


if __name__ == "__main__":
    unittest.main()

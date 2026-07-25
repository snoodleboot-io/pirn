"""Tests for :func:`pirn.domain_discovery.discover_installed_domains` (SCD-19)."""

from __future__ import annotations

# cross-domain: skipped in per-package isolation, run by the unified suite (SCD-24)
import pytest as _pytest
_pytest.importorskip("pirn_signal")
pytestmark = _pytest.mark.cross_domain

import unittest

from pirn.core.knot import Knot
from pirn.domain_discovery import discover_installed_domains
from sweet_tea.abstract_inverter_factory import AbstractInverterFactory


class TestDiscoverInstalledDomains(unittest.TestCase):
    def test_importable_from_public_module(self) -> None:
        # PIR-744: no longer re-exported at the pirn root; its public home is
        # the pirn.domain_discovery module.
        self.assertTrue(callable(discover_installed_domains))

    def test_returns_sorted_tuple_of_import_names(self) -> None:
        result = discover_installed_domains()
        self.assertIsInstance(result, tuple)
        self.assertEqual(list(result), sorted(result))
        # All six domain packages are installed in this environment.
        self.assertEqual(
            result,
            (
                "pirn_agents",
                "pirn_data",
                "pirn_health",
                "pirn_ml",
                "pirn_oilgas",
                "pirn_signal",
            ),
        )
        self.assertNotIn("pirn", result)

    def test_is_idempotent(self) -> None:
        first = discover_installed_domains()
        second = discover_installed_domains()
        self.assertEqual(first, second)

    def test_cross_domain_knots_resolve_by_bare_name(self) -> None:
        discover_installed_domains()
        data_knot = AbstractInverterFactory[Knot].create("date_dim_generator")
        signal_knot = AbstractInverterFactory[Knot].create("upsampler")
        self.assertTrue(issubclass(data_knot, Knot))
        self.assertTrue(issubclass(signal_knot, Knot))
        self.assertTrue(data_knot.__module__.startswith("pirn_data"))
        self.assertTrue(signal_knot.__module__.startswith("pirn_signal"))


if __name__ == "__main__":
    unittest.main()

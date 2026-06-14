"""Tests for the SCD-10 acyclic-DAG gate in ``scripts/check_import_graph.py``.

The script is a stand-alone gate (not an importable package), so it is loaded by
file path. Coverage:

* green-after on the real post-Phase-2 tree (the two broken edges are gone, the
  retained ``ml -> data`` edge survives);
* red-before behaviour synthesised in-memory — a cycle (C1) and an extra
  domain->domain edge (C3) are both caught;
* the PEP 508 distribution-name parser used by the declared-dependency check.
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "check_import_graph.py"


def _load_gate():
    spec = importlib.util.spec_from_file_location("check_import_graph", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_gate = _load_gate()


class TestDistributionName(unittest.TestCase):
    def test_strips_version_specifier(self) -> None:
        self.assertEqual(_gate._distribution_name("pirn-core>=0.4.0,<0.5.0"), "pirn-core")

    def test_strips_extras_and_marker(self) -> None:
        self.assertEqual(
            _gate._distribution_name('pirn-data[s3] >= 1.0 ; python_version >= "3.12"'),
            "pirn-data",
        )

    def test_bare_name_unchanged(self) -> None:
        self.assertEqual(_gate._distribution_name("pirn-ml"), "pirn-ml")


class TestFindCycle(unittest.TestCase):
    def test_acyclic_returns_none(self) -> None:
        edges = {"a": {"b"}, "b": {"c"}, "c": set()}
        self.assertIsNone(_gate._find_cycle(edges))

    def test_cycle_is_detected(self) -> None:
        edges = {"a": {"b"}, "b": {"c"}, "c": {"a"}}
        cycle = _gate._find_cycle(edges)
        self.assertIsNotNone(cycle)
        # A cycle path repeats its entry node at both ends.
        assert cycle is not None
        self.assertEqual(cycle[0], cycle[-1])


class TestDagViolations(unittest.TestCase):
    def test_sole_allowed_edge_passes(self) -> None:
        edges = {"ml": {"data"}, "data": set(), "agents": set(), "health": set()}
        self.assertEqual(
            _gate._dag_violations(edges, allowed_edge=("ml", "data"), kind="x"),
            [],
        )

    def test_extra_domain_edge_flagged(self) -> None:
        edges = {"ml": {"data"}, "agents": {"ml"}, "data": set()}
        violations = _gate._dag_violations(edges, allowed_edge=("ml", "data"), kind="x")
        self.assertTrue(any("'agents' -> 'ml'" in v for v in violations))

    def test_cycle_flagged(self) -> None:
        edges = {"ml": {"data"}, "data": {"ml"}}
        violations = _gate._dag_violations(edges, allowed_edge=("ml", "data"), kind="x")
        self.assertTrue(any("cycle" in v for v in violations))

    def test_missing_retained_edge_flagged(self) -> None:
        edges = {"ml": set(), "data": set()}
        violations = _gate._dag_violations(edges, allowed_edge=("ml", "data"), kind="x")
        self.assertTrue(any("retained edge" in v for v in violations))

    def test_domain_nodes_restricts_cross_edges(self) -> None:
        # core -> data is not a domain->domain edge when core is excluded.
        edges = {
            "pirn-core": set(),
            "pirn-ml": {"pirn-data", "pirn-core"},
            "pirn-data": {"pirn-core"},
        }
        domains = {"pirn-ml", "pirn-data", "pirn-agents"}
        self.assertEqual(
            _gate._dag_violations(
                edges, allowed_edge=("pirn-ml", "pirn-data"), kind="x", domain_nodes=domains
            ),
            [],
        )


class TestRealTreeGreenAfter(unittest.TestCase):
    """The post-Phase-2 tree must satisfy both DAG checks (no agents->ml,
    no health->agents, ml->data retained)."""

    def test_domain_import_dag_is_clean(self) -> None:
        src = _REPO_ROOT / "packages" / "pirn-core" / "src" / "pirn"
        self.assertEqual(_gate.check_domain_dag(src), [])

    def test_declared_package_dag_is_clean(self) -> None:
        packages = _REPO_ROOT / "packages"
        self.assertEqual(_gate.check_package_dag(packages), [])


if __name__ == "__main__":
    unittest.main()

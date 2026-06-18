"""Tests for the SCD-17 import codemod (``pirn._migrate.import_rewriter``).

Coverage:

* each of the six legacy import forms rewrites to the standalone ``pirn_<x>``
  spelling;
* aliases (``import ... as x`` / ``from pirn.domains import x as y``) survive;
* non-domain ``pirn.domains.<other>`` references are left untouched;
* idempotency — a second pass is a no-op fixed point;
* determinism — identical input yields byte-identical output every time;
* formatting (indentation, comments, surrounding code) is preserved.
"""

from __future__ import annotations

import unittest

from pirn._migrate.import_rewriter import ImportRewriter


class TestSixForms(unittest.TestCase):
    def setUp(self) -> None:
        self.rw = ImportRewriter()

    def test_import_module(self) -> None:
        self.assertEqual(
            self.rw.rewrite_text("import pirn.domains.signal\n"),
            "import pirn_signal\n",
        )

    def test_import_module_with_alias(self) -> None:
        self.assertEqual(
            self.rw.rewrite_text("import pirn.domains.oilgas as og\n"),
            "import pirn_oilgas as og\n",
        )

    def test_import_submodule(self) -> None:
        self.assertEqual(
            self.rw.rewrite_text("import pirn.domains.data.frames.batch\n"),
            "import pirn_data.frames.batch\n",
        )

    def test_from_domain_import_names(self) -> None:
        self.assertEqual(
            self.rw.rewrite_text("from pirn.domains.ml import Trainer, Model\n"),
            "from pirn_ml import Trainer, Model\n",
        )

    def test_from_submodule_import(self) -> None:
        self.assertEqual(
            self.rw.rewrite_text("from pirn.domains.health.mri import Volume\n"),
            "from pirn_health.mri import Volume\n",
        )

    def test_from_domains_import_bare(self) -> None:
        self.assertEqual(
            self.rw.rewrite_text("from pirn.domains import agents\n"),
            "import pirn_agents\n",
        )

    def test_from_domains_import_bare_with_alias(self) -> None:
        self.assertEqual(
            self.rw.rewrite_text("from pirn.domains import signal as sig\n"),
            "import pirn_signal as sig\n",
        )


class TestNonDomainsUntouched(unittest.TestCase):
    def setUp(self) -> None:
        self.rw = ImportRewriter()

    def test_non_domain_module_left_alone(self) -> None:
        src = "from pirn.domains.extras_loader import load\n"
        self.assertEqual(self.rw.rewrite_text(src), src)

    def test_non_domain_connectors_left_alone(self) -> None:
        src = "import pirn.domains.connectors\n"
        self.assertEqual(self.rw.rewrite_text(src), src)

    def test_domain_prefix_not_a_false_positive(self) -> None:
        # `datasource` starts with `data` but is a different module — the word
        # boundary must prevent rewriting it.
        src = "from pirn.domains.datasource import thing\n"
        self.assertEqual(self.rw.rewrite_text(src), src)

    def test_import_datasource_prefix_not_matched(self) -> None:
        src = "import pirn.domains.mlflow_bridge\n"
        self.assertEqual(self.rw.rewrite_text(src), src)

    def test_unrelated_lines_left_alone(self) -> None:
        src = "x = 1  # pirn.domains.signal mentioned in a comment\n"
        self.assertEqual(self.rw.rewrite_text(src), src)


class TestFormattingPreserved(unittest.TestCase):
    def setUp(self) -> None:
        self.rw = ImportRewriter()

    def test_indentation_preserved(self) -> None:
        self.assertEqual(
            self.rw.rewrite_text("    import pirn.domains.signal\n"),
            "    import pirn_signal\n",
        )

    def test_surrounding_code_preserved(self) -> None:
        src = (
            '"""Module docstring."""\n'
            "import os\n"
            "from pirn.domains.data import DataBatch\n"
            "\n"
            "VALUE = 1\n"
        )
        expected = (
            '"""Module docstring."""\nimport os\nfrom pirn_data import DataBatch\n\nVALUE = 1\n'
        )
        self.assertEqual(self.rw.rewrite_text(src), expected)

    def test_no_trailing_newline_preserved(self) -> None:
        self.assertEqual(
            self.rw.rewrite_text("import pirn.domains.ml"),
            "import pirn_ml",
        )


class TestIdempotencyAndDeterminism(unittest.TestCase):
    def setUp(self) -> None:
        self.rw = ImportRewriter()
        self.sample = (
            "import pirn.domains.signal\n"
            "import pirn.domains.oilgas as og\n"
            "from pirn.domains.data.frames import Batch\n"
            "from pirn.domains import ml\n"
            "from pirn.domains.extras_loader import load\n"
            "from pirn.domains.health import Scan\n"
            "from pirn.domains.agents import Agent as A\n"
        )

    def test_idempotent(self) -> None:
        once = self.rw.rewrite_text(self.sample)
        twice = self.rw.rewrite_text(once)
        self.assertEqual(once, twice)

    def test_already_migrated_is_fixed_point(self) -> None:
        migrated = "import pirn_signal\nfrom pirn_data import Batch\n"
        self.assertEqual(self.rw.rewrite_text(migrated), migrated)

    def test_deterministic(self) -> None:
        outputs = {ImportRewriter().rewrite_text(self.sample) for _ in range(5)}
        self.assertEqual(len(outputs), 1)

    def test_full_sample_expected_output(self) -> None:
        expected = (
            "import pirn_signal\n"
            "import pirn_oilgas as og\n"
            "from pirn_data.frames import Batch\n"
            "import pirn_ml\n"
            "from pirn.domains.extras_loader import load\n"
            "from pirn_health import Scan\n"
            "from pirn_agents import Agent as A\n"
        )
        self.assertEqual(self.rw.rewrite_text(self.sample), expected)


class TestRewriteFile(unittest.TestCase):
    def setUp(self) -> None:
        self.rw = ImportRewriter()

    def test_rewrite_file_reports_change(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mod.py"
            path.write_text("import pirn.domains.signal\n", encoding="utf-8")
            self.assertTrue(self.rw.rewrite_file(path))
            self.assertEqual(path.read_text(encoding="utf-8"), "import pirn_signal\n")
            # second run is a no-op
            self.assertFalse(self.rw.rewrite_file(path))

    def test_file_needs_rewrite(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mod.py"
            path.write_text("import pirn_signal\n", encoding="utf-8")
            self.assertFalse(self.rw.file_needs_rewrite(path))


if __name__ == "__main__":
    unittest.main()

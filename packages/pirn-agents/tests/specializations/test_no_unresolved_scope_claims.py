"""Guard: no ``specializations/`` docstring defers its own behaviour to elsewhere.

PIR-873 found four modules under ``specializations/`` whose docstrings excused a
missing capability by naming something outside the module:

* ``loaders/loader.py``, ``loaders/__init__.py``, ``pdf_loader.py`` and
  ``docx_loader.py`` said multimodal loading was "out of scope until F15
  merges" / "deferred to F15 (Phase 5, not merged)" — while ``MediaLoader``,
  the F15 loader, sat in the same directory, merged;
* ``parallel_specialist_fan_out.py`` and ``debate_framework.py`` said
  per-invocation error isolation "would need a core change and is out of
  scope" — while core's ``_inner_failures_reach_sink`` plus a
  ``RECEIVE_ERRORS`` fold is exactly that isolation, used by
  ``IngestionRunner`` in this package.

Both kinds of claim read as a limitation of the framework and were neither. A
docstring may absolutely record a deliberate design decision (all-or-nothing
failure, text-only extraction) — what it may not do is attribute the decision to
work that is supposedly not done yet. This guard fails on that phrasing, so the
next such excuse has to be either true and dated, or deleted.

It is a rule, not a list of blessed exceptions: there is nothing to add a new
finding to.
"""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

import pirn_agents.specializations as specializations_package


class TestNoUnresolvedScopeClaims(unittest.TestCase):
    """Every ``specializations/`` docstring owns its behaviour or explains it."""

    #: Phrases that attribute a missing capability to unfinished work elsewhere.
    _excuses: tuple[re.Pattern[str], ...] = (
        re.compile(r"out of scope", re.IGNORECASE),
        re.compile(r"not (yet )?merged", re.IGNORECASE),
        re.compile(r"until [A-Z]\d+ (merges|lands)", re.IGNORECASE),
        re.compile(r"(would |will )?need(s)? a core change", re.IGNORECASE),
        re.compile(r"not yet enforced by core", re.IGNORECASE),
        re.compile(r"deferred to [A-Z]\d+", re.IGNORECASE),
    )

    @staticmethod
    def _docstrings(path: Path) -> list[str]:
        """Every module, class and function docstring in ``path``."""
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        found: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                text = ast.get_docstring(node)
                if text:
                    found.append(text)
        return found

    def _modules(self) -> list[Path]:
        root = Path(specializations_package.__path__[0])
        return [path for path in sorted(root.rglob("*.py")) if "__pycache__" not in path.parts]

    def test_the_walk_is_not_vacuous(self) -> None:
        modules = self._modules()
        assert len(modules) > 300, len(modules)
        assert any(self._docstrings(path) for path in modules)

    def test_no_docstring_defers_its_behaviour_to_unfinished_work(self) -> None:
        offenders: list[str] = []
        for path in self._modules():
            for text in self._docstrings(path):
                for pattern in type(self)._excuses:
                    match = pattern.search(text)
                    if match is not None:
                        offenders.append(f"{path.name}: ...{match.group()}...")
        assert offenders == [], offenders


if __name__ == "__main__":
    unittest.main()

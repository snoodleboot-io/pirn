"""Missing-backend test for the optional flat ``ragas`` extra seam.

Asserts that :func:`load_ragas` raises the shared friendly ImportError (naming
the exact ``pip install`` command) when the backend is absent, without importing
it at module import time. Uses ``patch.dict`` on ``sys.modules`` so the test is
deterministic regardless of whether ``ragas`` happens to be installed.
"""

from __future__ import annotations

import builtins
import unittest
from collections.abc import Sequence
from typing import Any
from unittest.mock import patch

from pirn_agents.evaluation.ragas_backend import load_ragas

_real_import = builtins.__import__


def _import_without_ragas(
    name: str,
    globals_: Any = None,
    locals_: Any = None,
    fromlist: Sequence[str] = (),
    level: int = 0,
) -> Any:
    if name == "ragas" or name.startswith("ragas."):
        raise ImportError("No module named 'ragas'")
    return _real_import(name, globals_, locals_, fromlist, level)


class LoadRagasTests(unittest.TestCase):
    def test_missing_backend_raises_friendly_importerror(self) -> None:
        with patch.dict("sys.modules", {"ragas": None}):
            with patch("builtins.__import__", side_effect=_import_without_ragas):
                with self.assertRaises(ImportError) as ctx:
                    load_ragas()
        assert 'pip install "pirn-agents[ragas]"' in str(ctx.exception)


if __name__ == "__main__":
    unittest.main()

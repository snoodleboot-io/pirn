"""Tests for the shared ``_require`` lazy-import helper."""

from __future__ import annotations

import json
import unittest

from pirn_agents._require import _require


class TestRequire(unittest.TestCase):
    def test_returns_module_when_present(self) -> None:
        # Arrange / Act: ``json`` is stdlib and always importable.
        module = _require("web", "json")

        # Assert: the real module object is returned.
        assert module is json

    def test_missing_backend_raises_friendly_importerror(self) -> None:
        # Arrange / Act
        with self.assertRaises(ImportError) as ctx:
            _require("vector", "a_module_that_does_not_exist_xyz")

        # Assert: message names the exact install command.
        assert 'pip install "pirn-agents[vector]"' in str(ctx.exception)

    def test_missing_backend_chains_original_importerror(self) -> None:
        # Arrange / Act
        with self.assertRaises(ImportError) as ctx:
            _require("vector", "a_module_that_does_not_exist_xyz")

        # Assert: original ImportError is chained via ``from exc``.
        cause = ctx.exception.__cause__
        assert isinstance(cause, ImportError)


if __name__ == "__main__":
    unittest.main()

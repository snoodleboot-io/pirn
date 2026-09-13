"""Unit tests for :class:`ResolvedValueKnot`.

ADR agents-speaks-core WS5b: this shim is a ``Parameter`` subclass that
bypasses ``Knot.__init__`` entirely, so it is the concrete in-tree proof that
the ``Knot._deprecated_since`` seam (which lives in ``Knot._bootstrap``, not
``Knot.__init__``) fires for it too.
"""

from __future__ import annotations

import unittest
import warnings

from pirn.core.knot_config import KnotConfig
from pirn.tapestry import Tapestry

from pirn_agents.specializations.base.resolved_value_knot import ResolvedValueKnot


class TestResolvedValueKnotProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_the_configured_value(self) -> None:
        with Tapestry():
            knot = ResolvedValueKnot(value=42, _config=KnotConfig(id="rv"))
        result = await knot.process()
        assert result == 42


class TestResolvedValueKnotDeprecationNotice(unittest.TestCase):
    def test_construction_warns(self) -> None:
        with Tapestry(), warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            ResolvedValueKnot(value=1, _config=KnotConfig(id="rv"))
        assert len(caught) == 1
        assert issubclass(caught[0].category, DeprecationWarning)
        assert "ResolvedValueKnot" in str(caught[0].message)

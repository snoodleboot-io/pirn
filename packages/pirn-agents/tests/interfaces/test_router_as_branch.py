"""Tests for :meth:`Router.as_branch` (ADR agents-speaks-core WS5a).

``as_branch`` lets a pipeline wire a real core ``Branch`` + ``Aggregator``
fan-in instead of a Python ``if route == ...`` chain. See the method's own
docstring for the laziness caveat this suite also pins: every branch arm
executes regardless of selection, only the fused result picks the right one.
"""

from __future__ import annotations

import unittest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.interfaces.router import Router


class _Boom(Exception):
    pass


class _Raiser(Knot):
    async def process(self, **_: object) -> object:
        raise _Boom("arm failed")


class TestRouterAsBranch(unittest.IsolatedAsyncioTestCase):
    async def test_selects_the_matching_arm(self) -> None:
        with Tapestry() as t:
            route = Parameter("route", str, default="b", _config=KnotConfig(id="route"))
            Router.as_branch(
                route=route,
                branches={
                    "a": Parameter("arm_a", str, default="A", _config=KnotConfig(id="arm_a")),
                    "b": Parameter("arm_b", str, default="B", _config=KnotConfig(id="arm_b")),
                    "c": Parameter("arm_c", str, default="C", _config=KnotConfig(id="arm_c")),
                },
                _config=KnotConfig(id="fused"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["fused"] == "B"

    async def test_records_a_lineage_row_naming_the_selected_branch(self) -> None:
        with Tapestry() as t:
            route = Parameter("route", str, default="a", _config=KnotConfig(id="route"))
            Router.as_branch(
                route=route,
                branches={
                    "a": Parameter("arm_a", str, default="A", _config=KnotConfig(id="arm_a")),
                    "b": Parameter("arm_b", str, default="B", _config=KnotConfig(id="arm_b")),
                },
                _config=KnotConfig(id="fused"),
            )
        result = await t.run(RunRequest())
        select_record = next(row for row in result.lineage if row.knot_id == "fused:select")
        assert select_record.extra.get("selected_branch") == "a"

    async def test_rejects_empty_branches(self) -> None:
        with Tapestry():
            route = Parameter("route", str, default="a", _config=KnotConfig(id="route"))
            with self.assertRaises(TypeError):
                Router.as_branch(route=route, branches={}, _config=KnotConfig(id="fused"))

    async def test_selected_arm_failure_surfaces_as_err_with_the_real_message(self) -> None:
        with Tapestry() as t:
            route = Parameter("route", str, default="bad", _config=KnotConfig(id="route"))
            Router.as_branch(
                route=route,
                branches={
                    "ok": Parameter("arm_ok", str, default="fine", _config=KnotConfig(id="arm_ok")),
                    "bad": _Raiser(_config=KnotConfig(id="arm_bad")),
                },
                _config=KnotConfig(id="fused"),
            )
        result = await t.run(RunRequest())
        assert not result.succeeded
        fused_record = next(row for row in result.lineage if row.knot_id == "fused")
        assert fused_record.outcome == "err"

    async def test_a_non_selected_arm_still_executes(self) -> None:
        """Pins the documented laziness caveat: every arm runs regardless of selection."""
        calls: list[str] = []

        class _Counting(Knot):
            async def process(self, **_: object) -> str:
                calls.append(self.knot_id)
                return self.knot_id

        with Tapestry() as t:
            route = Parameter("route", str, default="a", _config=KnotConfig(id="route"))
            Router.as_branch(
                route=route,
                branches={
                    "a": _Counting(_config=KnotConfig(id="arm_a")),
                    "b": _Counting(_config=KnotConfig(id="arm_b")),
                },
                _config=KnotConfig(id="fused"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert set(calls) == {"arm_a", "arm_b"}


if __name__ == "__main__":
    unittest.main()

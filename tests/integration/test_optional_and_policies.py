"""Optional decorator and error-policy interaction tests."""

from __future__ import annotations

from typing import Any

import pytest
from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.optional import Optional
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.core.skipped import Skipped
from pirn.tapestry import Tapestry

pytestmark = pytest.mark.anyio


class Boom(Knot):
    """Always raises — used to exercise Optional failure paths."""

    async def process(self, x: int = 0, **_: Any) -> int:
        raise RuntimeError("not available")


class Echo(Knot):
    """Returns its input — used to exercise Optional success path."""

    async def process(self, x: int = 0, **_: Any) -> int:
        return x


def test_optional_result_is_knot():
    with Tapestry():
        opt = Optional(Boom, _config=KnotConfig(id="opt"))
    assert isinstance(opt, Knot)
    assert isinstance(opt, Optional)


async def test_optional_failure_produces_skipped_value():
    with Tapestry() as t:
        Optional(Boom, _config=KnotConfig(id="opt"))

    result = await t.run(RunRequest())
    assert isinstance(result.outputs["opt"], Skipped)
    assert "opt" not in result.skipped


async def test_optional_always_succeeds_on_failure():
    with Tapestry() as t:
        Optional(Boom, _config=KnotConfig(id="opt"))

    result = await t.run(RunRequest())
    assert "opt" in result.outputs
    assert "opt" not in result.skipped


async def test_optional_passes_value_through_on_success():
    with Tapestry() as t:
        p = Parameter("x", int, default=7, _config=KnotConfig(id="x"))
        Optional(Echo, x=p, _config=KnotConfig(id="opt"))

    result = await t.run(RunRequest())
    assert result.outputs["opt"] == 7


async def test_downstream_receives_skipped_value():
    @knot
    async def use(x: Any) -> bool:
        return isinstance(x, Skipped)

    with Tapestry() as t:
        opt = Optional(Boom, _config=KnotConfig(id="opt"))
        use(x=opt, _config=KnotConfig(id="use"))

    result = await t.run(RunRequest())
    assert result.outputs["use"] is True


async def test_receive_errors_policy_gets_results_directly():
    from pirn.core.err import Err
    from pirn.core.ok import Ok

    class HandleAny(Knot):
        async def process(self, x: object, **_: Any) -> str:
            if isinstance(x, Ok):
                return f"ok:{x.value}"
            if isinstance(x, Err):
                return f"err:{x.record.message}"
            return "skipped"

    with Tapestry() as t:
        p = Parameter("x", int, default=1, _config=KnotConfig(id="x"))
        b = Boom(x=p, _config=KnotConfig(id="b"))
        HandleAny(
            x=b,
            _config=KnotConfig(
                id="h",
                error_policy=ErrorPolicy.RECEIVE_ERRORS,
                validate_io=False,
            ),
        )

    result = await t.run(RunRequest())
    assert result.outputs["h"].startswith("err:")


async def test_require_all_parents_synthetic_err_on_skip():
    @knot
    async def use(x: int) -> int:
        return x + 1

    with Tapestry() as t:
        p = Parameter("x", int, default=1, _config=KnotConfig(id="x"))
        b = Boom(x=p, _config=KnotConfig(id="b"))
        use(
            x=b,
            _config=KnotConfig(
                id="u",
                error_policy=ErrorPolicy.REQUIRE_ALL_PARENTS,
            ),
        )

    result = await t.run(RunRequest())
    assert not result.succeeded
    by_id = {rec.knot_id: rec for rec in result.lineage}
    assert by_id["u"].outcome == "err"

"""Optional wrapper and error-policy interaction tests."""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.anyio

from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.optional import Optional
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry


@knot
async def boom(x: int) -> int:
    raise RuntimeError("not available")


def test_optional_is_knot():
    with Tapestry():
        inner = boom(x=Parameter("x", int), _config=KnotConfig(id="inner"))
        opt = Optional(knot=inner, _config=KnotConfig(id="opt"))
    assert isinstance(opt, Knot)
    assert isinstance(opt, Optional)


async def test_optional_failure_propagates_as_skipped():
    with Tapestry() as t:
        p = Parameter("x", int, default=5)
        inner = boom(x=p, _config=KnotConfig(id="inner"))
        Optional(knot=inner, _config=KnotConfig(id="opt"))

    result = await t.run(RunRequest())
    assert "opt" in result.skipped


async def test_optional_skipped_propagates_downstream():
    @knot
    async def use(x: int) -> int:
        return x + 1

    with Tapestry() as t:
        p = Parameter("x", int, default=5)
        inner = boom(x=p, _config=KnotConfig(id="inner"))
        opt = Optional(knot=inner, _config=KnotConfig(id="opt"))
        use(x=opt, _config=KnotConfig(id="use"))

    result = await t.run(RunRequest())
    assert "opt" in result.skipped
    assert "use" in result.skipped


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
        p = Parameter("x", int, default=1)
        b = boom(x=p, _config=KnotConfig(id="b"))
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
        p = Parameter("x", int, default=1)
        b = boom(x=p, _config=KnotConfig(id="b"))
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

"""Optional mixin and error-policy interaction tests."""

from __future__ import annotations

from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.core.knot import Knot
from pirn.core.optional import Optional
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.tapestry import Tapestry


class FetchOptional(Optional, Knot):
    """An optional knot that always fails; downstream should see Skipped."""

    async def process(self, x: int, **_: Any) -> int:
        raise RuntimeError("not available")


def test_optional_marks_class():
    p = Parameter("x", int)
    o = FetchOptional(x=p, _config=KnotConfig(id="o"))
    assert o.is_optional


async def test_optional_failure_propagates_as_skipped():
    """When an Optional knot fails, downstream sees the failure but the
    Skipped distinction is preserved in the LINEAGE.

    Note: The current engine implementation produces Err for the
    Optional knot itself (since it raised); downstream uses the Optional
    flag to interpret error_policy.  Verify the basic behaviour: the
    knot fails, and skip/err propagation works as the policy specifies.
    """

    @knot
    async def use(x: int) -> int:
        return x + 1

    with Tapestry() as t:
        p = Parameter("x", int, default=5)
        o = FetchOptional(x=p, _config=KnotConfig(id="o"))
        # Default policy: SKIP_IF_PARENT_FAILED — skip downstream.
        use(x=o, _config=KnotConfig(id="u"))

    result = await t.run(RunRequest())
    # The Optional knot failed.
    assert any(rec.knot_id == "o" for rec in result.exceptions)
    # Downstream is skipped.
    assert "u" in result.skipped


async def test_receive_errors_policy_gets_results_directly():
    """RECEIVE_ERRORS: the knot's process() receives Result objects."""
    from pirn.core.err import Err
    from pirn.core.ok import Ok

    @knot
    async def boom(x: int) -> int:
        raise ValueError("boom")

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
                validate_io=False,  # x: object accepts Result
            ),
        )

    result = await t.run(RunRequest())
    assert result.outputs["h"].startswith("err:")


async def test_require_all_parents_synthetic_err_on_skip():
    """REQUIRE_ALL_PARENTS: a skipped/failed parent → synthetic Err."""

    @knot
    async def boom(x: int) -> int:
        raise ValueError("boom")

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

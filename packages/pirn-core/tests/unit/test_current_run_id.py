"""Tests for the public ``current_run_id()`` accessor.

The run id has always been carried in a ContextVar, but only as the private
``_current_run_id``.  Downstream packages that want to correlate their own
telemetry with a run had to reach into that private name.  These tests pin the
public accessor's contract, including the two cases where it must degrade to
``None`` rather than lie: outside a run, and across a process boundary.
"""

from __future__ import annotations

import contextvars
import threading
import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.nodes.source import Source
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry, current_run_id

_seen: list[str | None] = []


@knot
async def _capture(x: int) -> int:
    """Record the run id visible from inside a knot's process()."""
    _seen.append(current_run_id())
    return x


class CurrentRunIdTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        _seen.clear()

    def test_returns_none_outside_a_run(self):
        """No run in flight means no run id — not a stale one, not a guess."""
        assert current_run_id() is None

    async def test_returns_the_run_id_during_a_run(self):
        with Tapestry() as t:
            p = Parameter("x", int)
            a = _capture(x=p, _config=KnotConfig(id="a"))

        request = RunRequest(parameters={"x": 1})
        result = await t.run(request, terminals=a)

        assert result.succeeded
        assert _seen == [request.run_id]

    async def test_resets_to_none_after_the_run(self):
        """The accessor must not leak the id past the run that set it."""
        with Tapestry() as t:
            p = Parameter("x", int)
            a = _capture(x=p, _config=KnotConfig(id="a"))

        await t.run(RunRequest(parameters={"x": 1}), terminals=a)

        assert current_run_id() is None

    async def test_survives_a_copy_context_thread_hop(self):
        """ThreadDispatcher hands work to threads via copy_context() (PIR-767).

        Work dispatched that way is still the same logical run, so the id must
        survive the hop.
        """
        with Tapestry() as t:
            p = Parameter("x", int)
            a = _capture(x=p, _config=KnotConfig(id="a"))

        request = RunRequest(parameters={"x": 1})
        hopped: list[str | None] = []

        @knot
        async def _hop(x: int) -> int:
            ctx = contextvars.copy_context()
            thread = threading.Thread(target=lambda: hopped.append(ctx.run(current_run_id)))
            thread.start()
            thread.join()
            return x

        with Tapestry() as t2:
            p2 = Parameter("x", int)
            b = _hop(x=p2, _config=KnotConfig(id="b"))

        await t2.run(request, terminals=b)

        assert hopped == [request.run_id]
        del t, a, p

    async def test_degrades_to_none_across_a_process_boundary(self):
        """A fresh interpreter has no context to copy.

        Ray/Dask/Celery workers start from an empty context, modelled here by
        running in a bare ``contextvars.Context()``.  The accessor must report
        None rather than a value inherited by accident.
        """
        with Tapestry() as t:
            p = Parameter("x", int)
            a = _capture(x=p, _config=KnotConfig(id="a"))

        seen: list[str | None] = []

        @knot
        async def _boundary(x: int) -> int:
            empty = contextvars.Context()
            thread = threading.Thread(target=lambda: seen.append(empty.run(current_run_id)))
            thread.start()
            thread.join()
            return x

        with Tapestry() as t2:
            p2 = Parameter("x", int)
            b = _boundary(x=p2, _config=KnotConfig(id="b"))

        await t2.run(RunRequest(parameters={"x": 1}), terminals=b)

        assert seen == [None]
        del t, a, p


class SubTapestryRunIdTests(unittest.IsolatedAsyncioTestCase):
    """Pin what the accessor reports inside a SubTapestry's inner run.

    The inner ``Tapestry.run()`` sets the var for its own run and reads the
    outer value only to record it as ``parent_run_id``, so a knot running
    inside the inner tapestry sees the *inner* id.  That is the behaviour a
    correlating caller has to reason about, so it is asserted rather than
    described.
    """

    async def test_inner_run_sees_the_inner_run_id(self):
        inner_seen: list[str | None] = []

        class _Inner(SubTapestry):
            async def process(self, **_: Any) -> Any:
                class _Leaf(Source):
                    async def process(self, **_kw: Any) -> int:
                        inner_seen.append(current_run_id())
                        return 1

                return _Leaf(_config=KnotConfig(id="leaf"))

        with Tapestry() as t:
            _Inner(_config=KnotConfig(id="inner"))

        outer_request = RunRequest()
        result = await t.run(outer_request)

        assert result.succeeded
        assert len(inner_seen) == 1
        assert inner_seen[0] is not None
        assert inner_seen[0] != outer_request.run_id, (
            "the inner run has its own id; if this ever equals the outer id, "
            "current_run_id()'s docstring is wrong"
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

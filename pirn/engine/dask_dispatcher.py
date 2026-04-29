"""Dask-backed dispatcher.

Submits each knot to a Dask distributed ``Client``.  Each knot becomes
a Dask task; results come back as ``pirn.Result`` instances.

Construction:

* ``DaskDispatcher(client=<dask.distributed.Client>)`` — inject an
  existing client (production / tests).
* ``DaskDispatcher(scheduler="tcp://...")`` — connect lazily on first
  use.
* ``DaskDispatcher.local()`` — convenience factory that builds an
  in-process ``LocalCluster`` for development.

Note on serialization: knots may hold callables, Pydantic models, and
arbitrary user values.  Dask uses cloudpickle by default which handles
most cases.  If a particular knot fails to serialize, refactor it to
hold only picklable references — or use ``LocalDispatcher`` /
``ThreadDispatcher`` for that knot.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.result import Result


class DaskDispatcher:
    """Run knots on a Dask cluster."""

    def __init__(self, client: Any = None, scheduler: str | None = None) -> None:
        if client is None and scheduler is None:
            raise TypeError("provide either client= or scheduler=")
        self._client = client
        self._scheduler = scheduler

    @classmethod
    def local(cls, **kwargs: Any) -> DaskDispatcher:
        """Build a dispatcher backed by an in-process LocalCluster."""
        try:
            from dask.distributed import Client, LocalCluster
        except ImportError as exc:
            raise ImportError(
                "DaskDispatcher requires dask[distributed]; install via "
                "`pip install pirn[dask]`"
            ) from exc
        cluster = LocalCluster(**kwargs)
        return cls(client=Client(cluster, asynchronous=True))

    @property
    def name(self) -> str:
        return "DaskDispatcher"

    async def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                from dask.distributed import Client
            except ImportError as exc:
                raise ImportError(
                    "DaskDispatcher requires dask[distributed]; install via "
                    "`pip install pirn[dask]`"
                ) from exc
            self._client = await Client(self._scheduler, asynchronous=True)
        return self._client

    async def dispatch(
        self, knot: Knot, inputs: Mapping[str, Any]
    ) -> Result[Any]:
        client = await self._ensure_client()
        # Submit a task that calls the knot and returns its Result.
        # Dask's Client.submit takes the function and its args; we wrap
        # the await in a sync helper so Dask workers don't need to run
        # an async loop.
        future = client.submit(_dask_run_knot, knot, dict(inputs))
        # Awaiting the future converts it from a Dask future to the
        # actual return value (or re-raises an exception).
        return await asyncio.wrap_future(future) if not hasattr(
            future, "__await__"
        ) else await future

    async def shutdown(self) -> None:
        if self._client is not None:
            await self._client.close()


def _dask_run_knot(knot: Knot, inputs: dict[str, Any]) -> Result[Any]:
    """Run a knot in a Dask worker process.

    Each worker has no event loop, so we spin one up via ``asyncio.run``
    for the duration of the knot call.  This mirrors ThreadDispatcher's
    approach.
    """
    return asyncio.run(knot(inputs))

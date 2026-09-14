"""Celery-backed dispatcher.

Submits each knot through a Celery app's ``send_task``.  The Celery
worker process must have registered the ``pirn.run_knot`` task and
have ``pirn`` itself importable; that's a one-time setup in the worker
init.

Unlike Dask and Ray (which can serialize most Python objects via
cloudpickle), Celery's default serializer is JSON.  We use
``pickle`` here because knots aren't JSON-serializable; this requires
configuring the Celery worker with ``task_serializer='pickle'``,
``accept_content=['pickle']``, and the standard pickle security
caveats (only run trusted code).

Construction:

* ``CeleryDispatcher(app=<celery.Celery>)`` - inject an app
  configured with the right serializer.
* ``CeleryDispatcher(broker_url="...", backend_url="...")`` - build
  one lazily.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from pirn.core.knot import Knot
from pirn.core.optional_dependency import OptionalDependency
from pirn.core.result import Result

if TYPE_CHECKING:
    from celery import Celery


class CeleryDispatcher:
    """Run knots on Celery workers."""

    _task_name = "pirn.run_knot"

    def __init__(
        self,
        *,
        app: Celery | None = None,
        broker_url: str | None = None,
        backend_url: str | None = None,
    ) -> None:
        if app is None and broker_url is None:
            raise TypeError("provide either app= or broker_url=")
        self._app: Celery | None = app
        self._broker_url = broker_url
        self._backend_url = backend_url

    @property
    def name(self) -> str:
        return "CeleryDispatcher"

    def _ensure_app(self) -> Celery:
        if self._app is None:
            celery = OptionalDependency.require("celery", extra="celery")
            app: Celery = celery.Celery(
                "pirn",
                broker=self._broker_url,
                backend=self._backend_url or self._broker_url,
            )
            app.conf.update(
                task_serializer="pickle",
                accept_content=["pickle"],
                result_serializer="pickle",
            )
            self._app = app
        return self._app

    async def dispatch(self, knot: Knot, inputs: Mapping[str, Any]) -> Result[Any]:
        app = self._ensure_app()
        async_result = app.send_task(
            self._task_name,
            args=(knot, dict(inputs)),
        )
        # Celery's get() is blocking; bridge to async.  The worker task is
        # ``_run_knot_sync``, whose return value is the knot's ``Result``.
        outcome: Result[Any] = await asyncio.to_thread(async_result.get)
        return outcome

    @staticmethod
    def _run_knot_sync(knot: Knot, inputs: dict[str, Any]) -> Result[Any]:
        """Worker-side entry point that runs a knot synchronously.

        Celery worker processes have no event loop, so we spin one up
        via ``asyncio.run``.  Implemented as ``@staticmethod`` so it
        belongs to the dispatcher class while remaining picklable: the
        Celery worker resolves it by qualified name through a normal
        import of ``pirn.engine.dispatchers.celery_dispatcher``.
        """
        return asyncio.run(knot(inputs))

    @classmethod
    def register_worker_task(cls, app: Celery) -> None:
        """Register the ``pirn.run_knot`` task on a Celery app.

        Call this from the Celery worker's startup code so workers know
        how to run knots.
        """
        app.task(name=cls._task_name)(cls._run_knot_sync)

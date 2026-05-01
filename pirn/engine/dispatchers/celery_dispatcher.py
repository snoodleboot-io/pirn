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
from typing import Any

from pirn.core.knot import Knot
from pirn.core.result import Result


class CeleryDispatcher:
    """Run knots on Celery workers."""

    _task_name = "pirn.run_knot"

    def __init__(
        self,
        *,
        app: Any = None,
        broker_url: str | None = None,
        backend_url: str | None = None,
    ) -> None:
        if app is None and broker_url is None:
            raise TypeError("provide either app= or broker_url=")
        self._app = app
        self._broker_url = broker_url
        self._backend_url = backend_url

    @property
    def name(self) -> str:
        return "CeleryDispatcher"

    def _ensure_app(self) -> Any:
        if self._app is None:
            try:
                from celery import Celery
            except ImportError as exc:
                raise ImportError(
                    "CeleryDispatcher requires celery; install via `pip install pirn[celery]`"
                ) from exc
            self._app = Celery(
                "pirn",
                broker=self._broker_url,
                backend=self._backend_url or self._broker_url,
            )
            self._app.conf.update(
                task_serializer="pickle",
                accept_content=["pickle"],
                result_serializer="pickle",
            )
        return self._app

    async def dispatch(self, knot: Knot, inputs: Mapping[str, Any]) -> Result[Any]:
        app = self._ensure_app()
        async_result = app.send_task(
            self._task_name,
            args=(knot, dict(inputs)),
        )
        # Celery's get() is blocking; bridge to async.
        return await asyncio.to_thread(async_result.get)

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
    def register_worker_task(cls, app: Any) -> None:
        """Register the ``pirn.run_knot`` task on a Celery app.

        Call this from the Celery worker's startup code so workers know
        how to run knots.
        """
        app.task(name=cls._task_name)(cls._run_knot_sync)


def register_celery_worker_task(app: Any) -> None:
    """Register the ``pirn.run_knot`` task on a Celery app.

    Thin wrapper around :meth:`CeleryDispatcher.register_worker_task`
    kept as a top-level entry for external worker bootstraps:

    .. code-block:: python

        from celery import Celery
        from pirn.engine.dispatchers.celery_dispatcher import register_celery_worker_task

        app = Celery(...)
        app.conf.update(
            task_serializer="pickle",
            accept_content=["pickle"],
            result_serializer="pickle",
        )
        register_celery_worker_task(app)
    """
    CeleryDispatcher.register_worker_task(app)

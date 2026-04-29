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

* ``CeleryDispatcher(app=<celery.Celery>)`` — inject an app
  configured with the right serializer.
* ``CeleryDispatcher(broker_url="...", backend_url="...")`` — build
  one lazily.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.result import Result

# Task name used on the worker side; symmetrical between dispatcher and
# worker so they agree on what to call.
PIRN_CELERY_TASK_NAME = "pirn.run_knot"


class CeleryDispatcher:
    """Run knots on Celery workers."""

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
            PIRN_CELERY_TASK_NAME,
            args=(knot, dict(inputs)),
        )
        # Celery's get() is blocking; bridge to async.
        return await asyncio.to_thread(async_result.get)


def register_celery_worker_task(app: Any) -> None:
    """Register the ``pirn.run_knot`` task on a Celery app.

    Call this from the Celery worker's startup code so workers know how
    to run knots:

    .. code-block:: python

        from celery import Celery
        from pirn.engine.celery_dispatcher import register_celery_worker_task

        app = Celery(...)
        app.conf.update(
            task_serializer="pickle",
            accept_content=["pickle"],
            result_serializer="pickle",
        )
        register_celery_worker_task(app)
    """

    @app.task(name=PIRN_CELERY_TASK_NAME)
    def _run_knot(knot: Knot, inputs: dict[str, Any]) -> Result[Any]:
        return asyncio.run(knot(inputs))

    return _run_knot

"""Sink — terminal consumer.

A ``Sink`` is a knot whose output is conventionally ``None``.  Used to
push values to external systems: write a file, post to an API, publish
to a queue.

Functionally a Sink is just a Knot.  The class exists for taxonomy and
visualisation: pirn's tooling (in Phase 3) renders sinks differently
from regular knots.
"""

from __future__ import annotations

from pirn.core.knot import Knot


class Sink(Knot):
    """Base class for terminal consumers that push values to external systems.

    A ``Sink`` sits at the end of a pipeline and has no downstream knots that
    depend on it within the same tapestry.  Its ``process()`` return value is
    conventionally ``None``, but a confirmation receipt or similar value is
    permitted.  Typical uses: write a file, post to an API, publish to a queue.

    Subclass and implement ``async def process(self, ...) -> None``.  Follow
    the two-layer knot pattern: declare all inputs as ``Knot | scalar_type``
    in ``__init__`` and as resolved plain types in ``process()``.

    Algorithm:
        1. Declaration — subclass declares upstream data knots and configuration
           inputs as ``Knot | scalar_type`` in ``__init__``.  Plain scalars are
           auto-coerced to ``Parameter`` nodes by the base ``Knot.__init__``.
        2. Scheduling — the engine resolves all parent knots concurrently.
           Because a ``Sink`` is typically a leaf in the DAG, the engine
           includes it in the run's terminal set and ensures it completes.
        3. Execution — ``process()`` receives resolved values for all declared
           inputs and performs the side-effecting write or publish operation.
        4. Output — the return value (usually ``None``) is wrapped in ``Ok``
           and stored in the run result; it is available for inspection but
           is not typically consumed by other knots.

    Example::

        class WriteUsers(Sink):
            def __init__(
                self,
                *,
                users: Knot,
                path: Knot | str,
                _config: KnotConfig,
                **kwargs: Any,
            ) -> None:
                super().__init__(users=users, path=path, _config=_config, **kwargs)

            async def process(self, users: list[dict], path: str, **_: Any) -> None:
                with open(path, "w") as f:
                    json.dump(users, f)

        with Tapestry() as t:
            users = ...
            WriteUsers(
                users=users,
                path="/tmp/out.json",
                _config=KnotConfig(id="write"),
            )
    """

"""Sink — terminal consumer.

A ``Sink`` is a knot whose output is conventionally ``None``.  Used to
push values to external systems: write a file, post to an API, publish
to a queue.

Functionally a Sink is just a Knot.  The class exists for taxonomy and
visualisation: pirn's tooling (in Phase 3) renders sinks differently
from regular knots.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class Sink(Knot):
    """Base class for terminal consumers.

    Subclass and implement ``async def process(self, ...) -> None``.  The
    return type is conventionally None but not enforced — a sink that
    returns a confirmation receipt is fine.

    Follow the two-layer knot pattern: declare all inputs as
    ``Knot | scalar_type`` in ``__init__`` and as resolved plain types
    in ``process()``.

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

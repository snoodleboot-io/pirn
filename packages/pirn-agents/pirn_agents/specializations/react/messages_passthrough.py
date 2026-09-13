"""``MessagesPassthrough`` — deprecated for the constant-seed case.

Historically used two ways: (a) seeding a loop's first knot from an
already-known ``tuple``/``list`` of messages — this is exactly
:class:`~pirn.core.parameter.Parameter`'s job (see ``react_loop.py``'s
``seed = Parameter("seed_messages", tuple[AgentMessage, ...], ...)``), so this
class no longer has an in-tree caller for it — or (b) wiring an *upstream*
``Knot`` whose eventual output should be coerced from a list to a tuple.

``Parameter`` cannot express case (b): it is a graph root with no parents, so
it cannot accept an upstream ``Knot`` as its value the way this class's
``messages: Knot | tuple | list`` signature does (core gap noted in the
ADR agents-speaks-core WS5a report — a generic "coerce this knot's output"
transform has no core primitive of its own). That branch is kept, unchanged,
so this class stays behaviourally correct for any external caller passing a
real ``Knot``; only the constant-seed idiom is deprecated.

No runtime ``DeprecationWarning`` is raised (docstring-only deprecation): Knot
Design Rule 1 forbids any ``__init__`` statement beyond a single
``super().__init__(...)`` call for a class subclassing ``Knot`` directly
(``scripts/check_conventions.py``'s ``knot_init_impure`` rule), and a
``__new__``-based warning is not a workaround — ``Knot.run_scoped_copy`` calls
``copy.copy(self)`` on every knot before every run, which reconstructs via
``cls.__new__(cls)`` with no arguments, so a ``__new__`` requiring
``messages``/``_config`` breaks every run through this knot. Same core-tooling
gap as ``ResolvedValueKnot``; see its module docstring.

Algorithm:
    1. Receive the resolved ``messages`` collection at process time.
    2. Convert the collection to an immutable tuple.
    3. Return the tuple unchanged.


References:
    - pirn-native identity pattern; no external algorithm reference.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.types.messaging.agent_message import AgentMessage


class MessagesPassthrough(Knot):
    """Identity knot that re-exposes a tuple of :class:`AgentMessage`.

    Deprecated for seeding a loop from an already-known constant — construct
    a :class:`~pirn.core.parameter.Parameter` directly instead (see the module
    docstring). Still the correct choice when ``messages`` is a genuine
    upstream ``Knot`` whose list output must be coerced to a tuple.
    """

    def __init__(
        self,
        *,
        messages: Knot | tuple[AgentMessage, ...] | list[AgentMessage],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(messages=messages, _config=_config, **kwargs)

    async def process(
        self,
        messages: tuple[AgentMessage, ...] | list[AgentMessage],
        **_: Any,
    ) -> tuple[AgentMessage, ...]:
        """Convert the input messages collection to a tuple and return it unchanged.

        Args:
            messages: The list or tuple of AgentMessage instances to pass through.

        Returns:
            The same messages as an immutable tuple.
        """
        return tuple(messages)

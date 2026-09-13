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

A runtime ``DeprecationWarning`` is now raised for the deprecated (constant-seed)
call shape only, via ``Knot._deprecated_since`` / ``Knot._deprecation_notice``
(ADR agents-speaks-core WS5b): ``_deprecation_notice`` is overridden below to
inspect whether ``messages`` was wired in as a parent (a real upstream
``Knot`` — still correct, stays silent) or a config value (the constant-seed
idiom being deprecated), so the same class can warn for one call shape and not
the other without ``__init__`` containing anything beyond its required single
``super().__init__(...)`` call (Rule 1, ``knot-design-rules.md``, enforced by
``scripts/check_conventions.py``'s ``knot_init_impure`` rule). Same
core-tooling gap ``ResolvedValueKnot`` names — see its module docstring — now
resolved by the same seam.

Algorithm:
    1. Receive the resolved ``messages`` collection at process time.
    2. Convert the collection to an immutable tuple.
    3. Return the tuple unchanged.


References:
    - pirn-native identity pattern; no external algorithm reference.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.types.messaging.agent_message import AgentMessage


class MessagesPassthrough(Knot):
    """Identity knot that re-exposes a tuple of :class:`AgentMessage`.

    Deprecated for seeding a loop from an already-known constant — construct
    a :class:`~pirn.core.parameter.Parameter` directly instead (see the module
    docstring). Still the correct choice when ``messages`` is a genuine
    upstream ``Knot`` whose list output must be coerced to a tuple; that call
    shape does not warn (see :meth:`_deprecation_notice`).
    """

    _deprecated_since: ClassVar[str | None] = "agents-speaks-core WS5a"

    def __init__(
        self,
        *,
        messages: Knot | tuple[AgentMessage, ...] | list[AgentMessage],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(messages=messages, _config=_config, **kwargs)

    def _deprecation_notice(
        self, parents: Mapping[str, Knot], config_values: Mapping[str, Any]
    ) -> str | None:
        """Warn only for the constant-seed idiom, not a genuine upstream ``Knot``.

        ``messages`` lands in ``parents`` when the caller wired an upstream
        ``Knot`` (still correct — that branch is not deprecated) and in
        ``config_values`` when the caller passed an already-known
        tuple/list (the idiom :class:`~pirn.core.parameter.Parameter` replaces).
        """
        if "messages" in parents:
            return None
        return type(self)._deprecated_since

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

"""``interfaces`` — shared role-family base abstractions for pirn-agents.

A neutral, sibling package holding the cross-cutting role bases that several
domains implement: :class:`~pirn_agents.interfaces.retriever.Retriever`,
:class:`~pirn_agents.interfaces.writer.Writer`, and
:class:`~pirn_agents.interfaces.router.Router`. Each is a
:class:`~pirn.core.knot.Knot` subclass whose ``process`` raises
:class:`NotImplementedError` (the house interface style — never
:class:`typing.Protocol`).

The bases live here, rather than under ``memory/`` or ``retrieval/``, so that a
consumer in any one domain depends *sideways* on a neutral abstraction instead
of *upward* into a peer (which would invert the dependency graph — e.g.
``memory`` importing ``specializations``). Every concrete retriever, writer, or
router across the package rebases onto the matching abstraction here, so callers
depend on the role, not the concrete (DIP), and every concrete stays
substitutable for its role base (LSP).

Import each base from its concrete module (``pirn_agents.interfaces.retriever``,
``...router``, ``...writer``) — this package does not re-export them.
"""

__all__: list[str] = []

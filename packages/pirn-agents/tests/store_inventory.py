"""``StoreInventory`` — every ``pirn_agents`` knot that keeps a keyed store of its own.

ADR "agents speaks core" WS3 moves memory, sessions and determinism onto core's
value and lineage planes: ``DataStore`` is the key→value plane and
``RunHistory``/``KnotLineage`` the durable ledger. A class that keeps its own
``dict`` and offers put/get over it is a second value plane — invisible to a
run's replay, its lineage, its identity resolution and its data store, and
unshared between the knots that need the same value.

Detection is the *shape*, not a method-name list. The version this replaced
asked whether a class's runtime method surface contained one of three name pairs
(``store``/``retrieve``, ``put``/``get``, ``save``/``load``) or a ``search``
beside one of them — so a store spelled ``register``/``get``, ``add``/``lookup``,
``upsert``/``fetch``, or anything else was invisible to it, and
``tools/tool_registry.py``'s ``register``/``get`` store (among others) never
appeared in the inventory it was supposed to freeze. What makes something a store
is structural: it writes an attribute of its own under a run-time key and reads it
back under one. That is
:meth:`~tests.source_shapes.SourceShapes.keyed_store_attributes`, and it does not
care what the two methods are called.

The rule is scoped to ``Knot`` subclasses, and the reason is where the value
plane is: it is where a *knot's output* goes. A knot that stashes run values in a
dict of its own keeps them out of replay, lineage and identity resolution — that
is the defect. A class that is not a knot is a data structure the knot reaches
through a declared input; its dict is its implementation, exactly as core's
``InMemoryDataStore`` keeps ``_values`` and ``_evicted`` — the one true value
plane has the identical shape, so the shape alone cannot be the rule. The shape is
right and :meth:`~tests.source_shapes.SourceShapes.keyed_store_attributes` is
unchanged; only the scope was wrong. What the rule correctly no longer flags:

- in-memory backends of a store interface (``InMemoryGraphStore``,
  ``InMemoryVectorStore``): the thing the interface promises, as core's own is;
- registries and pools of live collaborators keyed by name (``ToolRegistry``,
  ``PromptTemplateRegistry``, ``CircuitBreakerRegistry``, ``McpSessionPool``,
  ``AgentReferences``, ``AgentBuilder``): a factory, template, breaker, session or
  agent is not a serialisable run value and the ``DataStore`` could not hold one;
- algorithmic indexes (``Bm25Index``, ``SimilarityIndex``): search structures, and
  similarity search is explicitly not what the ``DataStore`` does;
- caches (``TokenCounter``, ``SingleFlight``): recomputable memos.

A class that delegates to a real backend — a ``DataStore``, or an external
service's client — never subscripts a mapping of its own and is not a store.
"""

from __future__ import annotations

from tests.agents_source_index import AgentsSourceIndex
from tests.source_shapes import SourceShapes


class StoreInventory:
    """Discovers the knots that hold a key→value plane of their own."""

    @staticmethod
    def discover() -> dict[str, frozenset[str]]:
        """Return ``{"relative/path.py::ClassName": {store attribute, ...}}``.

        One walk of the package (see
        :class:`~tests.agents_source_index.AgentsSourceIndex`); every ``Knot``
        subclass is scanned, no directory list and no name list scopes it.
        """
        found: dict[str, frozenset[str]] = {}
        for label, (_subject, node) in AgentsSourceIndex.knots().items():
            stores = SourceShapes.keyed_store_attributes(node)
            if stores:
                found[label] = stores
        return found

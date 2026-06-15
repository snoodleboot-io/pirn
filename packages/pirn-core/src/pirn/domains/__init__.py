"""Pirn domain knot libraries.

Each subpackage under ``pirn.domains`` ships a curated, auto-discovered
collection of knots for a specific problem domain. Discovery happens at
import time of the top-level :mod:`pirn` package via
``sweet_tea.registry.Registry.fill_registry()``; every Knot subclass below
becomes resolvable by name through
:class:`sweet_tea.abstract_inverter_factory.AbstractInverterFactory[Knot]`.

- ``pirn.connectors``  — Cross-cutting Source/Sink connectors

The domain knot libraries are shipped as separate packages: ``pirn_signal``,
``pirn_oilgas``, ``pirn_agents``, ``pirn_data``, ``pirn_ml``, and
``pirn_health`` (e.g. ``pip install pirn-data pirn-ml pirn-health``). Only
``pirn.connectors`` remains in core.

Heavy dependencies for each domain are isolated via optional extras. Install
only the domains you use::

    pip install pirn[data]
    pip install pirn[health]
    pip install pirn[all-domains]

User projects that define their own ``Knot`` subclasses must call
``Registry.fill_registry()`` from their own package init for those classes
to appear in the resolver — pirn only auto-discovers its own tree.
"""

__all__: list[str] = []

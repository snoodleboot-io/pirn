"""Pirn domain knot libraries.

Each subpackage under ``pirn.domains`` ships a curated, auto-discovered
collection of knots for a specific problem domain. Discovery happens at
import time of the top-level :mod:`pirn` package via
``sweet_tea.registry.Registry.fill_registry()``; every Knot subclass below
becomes resolvable by name through
:class:`sweet_tea.abstract_inverter_factory.AbstractInverterFactory[Knot]`.

- ``pirn.connectors``  — Cross-cutting Source/Sink connectors
- ``pirn.domains.health``      — Healthcare / Genomics / Imaging / EEG/MEG

The Digital Signal Processing, Oil & Gas, Agentic Pipelines / Patterns, Data
Engineering, and ML domains are shipped separately as the ``pirn_signal``,
``pirn_oilgas``, ``pirn_agents``, ``pirn_data``, and ``pirn_ml`` packages
(``pip install pirn-signal pirn-oilgas pirn-agents pirn-data pirn-ml``).

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

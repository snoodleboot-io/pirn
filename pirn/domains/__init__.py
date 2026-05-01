"""Pirn domain knot libraries.

Each subpackage under ``pirn.domains`` ships a curated, KnotRegistry-registered
collection of knots for a specific problem domain:

- ``pirn.domains.data``        — Data Engineering / Analytics Engineering
- ``pirn.domains.agents``      — Agentic Pipelines / Patterns
- ``pirn.domains.ml``          — ML Engineering / Data Science
- ``pirn.domains.connectors``  — Cross-cutting Source/Sink connectors
- ``pirn.domains.health``      — Healthcare / Genomics / Imaging / EEG/MEG
- ``pirn.domains.signal``      — Digital Signal Processing
- ``pirn.domains.oilgas``      — Oil & Gas

Heavy dependencies for each domain are isolated via optional extras. Install
only the domains you use::

    pip install pirn[data]
    pip install pirn[health,signal]
    pip install pirn[all-domains]
"""

__all__: list[str] = []

"""Agentic Pipelines / Patterns knot library.

Install with::

    pip install 'pirn[agents]'

The agents domain has no heavy core dependencies — concrete LLM, memory, and
tool providers are user-supplied via the protocols defined in
``pirn.domains.agents.protocols``.

See ``planning/current/domain-knot-libraries-prd.md`` for the full catalog.
"""

# No required extras — providers are user-supplied via protocols.
# Knot modules will be imported here as they land.

__all__: list[str] = []

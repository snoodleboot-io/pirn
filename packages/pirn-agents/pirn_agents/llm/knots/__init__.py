"""Vending knots for the LLM-provider domain.

Nests the LLM-provider :class:`~pirn.core.knot.Knot` adapters under their domain
(mirroring core's ``connectors/knots/`` layout). Ships
:class:`~pirn_agents.llm.knots.llm_provider_knot.LLMProviderKnot`, the
pass-through knot that vends a pooled LLM provider through the graph. Importing
this subpackage pulls in no backend.
"""

from __future__ import annotations

"""LLM provider connectors (PAE-F3 / PIR-16).

Concrete :class:`pirn_agents.llm.llm_provider.LLMProvider` implementations
built on the shared :class:`pirn_agents.llm.base_llm_provider.BaseLLMProvider`.
Every provider is a peer plugin behind an optional extra; importing this
package pulls in **no** backend (the HTTP client is imported lazily via
:meth:`~pirn.core.optional_dependency.OptionalDependency.require`). See ``LLM_PROVIDERS.md`` for the extras
matrix, usage, and local/self-hosted (vLLM/Ollama) validation notes.
"""

from __future__ import annotations

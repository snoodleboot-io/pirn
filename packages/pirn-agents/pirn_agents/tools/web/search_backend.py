"""``SearchBackend`` — provider-neutral interface for a web-search API.

:class:`~pirn_agents.tools.web.web_search_tool.WebSearchTool` delegates to an
injected :class:`SearchBackend`, so no search vendor is hard-wired. Concrete
backends (a hosted search API, a local index, a test double) implement
:meth:`search` and return an ordered sequence of result mappings; the tool
normalises them to ``{title, url, snippet}`` records.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


class SearchBackend(PirnOpaqueValue):
    """Interface every web-search backend must satisfy."""

    async def search(self, query: str, *, max_results: int) -> Sequence[Mapping[str, Any]]:
        """Return up to ``max_results`` result mappings for ``query``.

        Each mapping should carry at least ``title`` and ``url`` keys, and
        optionally ``snippet``. Ordering is treated as the ranking.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement search()")

"""``EmbeddedTexts`` — embed one level's texts as a knot, not as a loop's await.

One batched ``embed`` call, declared inside the level's own tapestry so it has a
``Result``, a retry, a timeout and a lineage row of its own. It was an ``await``
inside :class:`RaptorAssembler`'s ``while`` loop, which is a collaborator call
the run could not see however many levels the tree had (Rule 11; PIR-874).

The call stays *one* request: the provider batches a level's texts, and splitting
it into a knot per text would make N requests where the provider wants one.

Internal API. See ``raptor_level_loop.py``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.retrieval.embeddings.embedding_provider import EmbeddingProvider


class EmbeddedTexts(Knot):
    """Ask the embedding provider for one vector per text, in one request."""

    def __init__(
        self,
        *,
        embedder: Knot | EmbeddingProvider,
        texts: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(embedder=embedder, texts=texts, _config=_config, **kwargs)

    async def process(
        self,
        embedder: EmbeddingProvider,
        texts: Sequence[str],
        **_: Any,
    ) -> tuple[tuple[float, ...], ...]:
        """Embed ``texts`` and return one immutable vector per text, in order.

        Args:
            embedder: The provider producing the vectors.
            texts: The texts to embed.

        Returns:
            One vector per text, in the same order.
        """
        vectors = await embedder.embed(list(texts))
        return tuple(tuple(vector) for vector in vectors)

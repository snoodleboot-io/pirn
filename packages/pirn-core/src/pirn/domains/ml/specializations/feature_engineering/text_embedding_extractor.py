"""``TextEmbeddingExtractor`` — wrap the core :class:`EmbeddingExtractor`
knot for a text column on every partition of a :class:`SplitManifest`.

Composition: a single :class:`EmbeddingExtractor` step appends a
``<text_column>_embedding`` feature to the train / validation / test
partitions of the upstream split.

Algorithm:
    1. Receive ``split`` (SplitManifest), ``text_column``, and
       ``embedding_provider`` via process().
    2. Validate all inputs.
    3. Wire EmbeddingExtractor in an inner Tapestry.
    4. Run via _run_inner() and return the updated SplitManifest.


References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.providers.embedding_provider import EmbeddingProvider
from pirn.domains.ml.features.embedding_extractor import EmbeddingExtractor
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.nodes.sub_tapestry import SubTapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


class TextEmbeddingExtractor(SubTapestry):
    """Append a text-column embedding feature to every split partition."""

    def __init__(
        self,
        *,
        split: Knot,
        text_column: Knot | str,
        embedding_provider: Knot | EmbeddingProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            text_column=text_column,
            embedding_provider=embedding_provider,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: SplitManifest,
        text_column: str = "",
        embedding_provider: EmbeddingProvider | None = None,
        **_: Any,
    ) -> Any:
        """Embed the text column via the embedding provider, append the feature to each partition, and return the updated SplitManifest.

        Args:
            split: SplitManifest whose partitions receive the new text embedding feature.
            text_column: Non-empty name of the text column to embed.
            embedding_provider: EmbeddingProvider instance to use for embedding.

        Returns:
            SplitManifest with ``<text_column>_embedding`` appended to every partition's feature list.

        Raises:
            ValueError: If text_column is empty.
            TypeError: If embedding_provider is not an EmbeddingProvider or the inner extractor does not return a SplitManifest.
        """
        if not isinstance(text_column, str) or not text_column:
            raise ValueError("TextEmbeddingExtractor: text_column must be a non-empty string")
        if not isinstance(embedding_provider, EmbeddingProvider):
            raise TypeError(
                "TextEmbeddingExtractor: embedding_provider must be an EmbeddingProvider"
            )
        split_node = _emit_value(value=split, _config=KnotConfig(id="split"))
        return EmbeddingExtractor(
            split=split_node,
            text_column=text_column,
            embedding_provider=embedding_provider,
            _config=KnotConfig(id="embed"),
        )

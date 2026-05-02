"""``TextEmbeddingExtractor`` — wrap the core :class:`EmbeddingExtractor`
knot for a text column on every partition of a :class:`DataSplit`.

Composition: a single :class:`EmbeddingExtractor` step appends a
``<text_column>_embedding`` feature to the train / validation / test
partitions of the upstream split.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.ml.embedding_provider import EmbeddingProvider
from pirn.domains.ml.features.embedding_extractor import EmbeddingExtractor
from pirn.domains.ml.types.data_split import DataSplit
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


class TextEmbeddingExtractor(SubTapestry):
    """Append a text-column embedding feature to every split partition."""

    def __init__(
        self,
        *,
        split: Knot,
        text_column: str,
        embedding_provider: EmbeddingProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(split, Knot):
            raise TypeError("TextEmbeddingExtractor: split must be a Knot")
        if not isinstance(text_column, str) or not text_column:
            raise ValueError(
                "TextEmbeddingExtractor: text_column must be a non-empty "
                "string"
            )
        if not isinstance(embedding_provider, EmbeddingProvider):
            raise TypeError(
                "TextEmbeddingExtractor: embedding_provider must be an "
                "EmbeddingProvider"
            )
        self._text_column = text_column
        self._embedding_provider = embedding_provider
        super().__init__(split=split, _config=_config, **kwargs)

    async def process(self, split: DataSplit, **_: Any) -> DataSplit:
        with Tapestry() as inner:
            split_node = _emit_value(
                value=split, _config=KnotConfig(id="split")
            )
            EmbeddingExtractor(
                split=split_node,
                text_column=self._text_column,
                embedding_provider=self._embedding_provider,
                _config=KnotConfig(id="embed"),
            )
        result = await self._run_inner(inner)
        embedded = result.outputs["embed"]
        if not isinstance(embedded, DataSplit):
            raise TypeError(
                "TextEmbeddingExtractor: inner extractor did not return a "
                "DataSplit"
            )
        return embedded

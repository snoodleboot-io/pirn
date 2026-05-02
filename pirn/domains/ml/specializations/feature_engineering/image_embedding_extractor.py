"""``ImageEmbeddingExtractor`` — append an image-column embedding feature
to every partition of a :class:`DataSplit` via an
:class:`ImageEncoderProvider`.

Mirrors :class:`TextEmbeddingExtractor` but operates over image bytes
through an :class:`ImageEncoderProvider`.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.domains.ml.image_encoder_provider import ImageEncoderProvider
from pirn.domains.ml.specializations.feature_engineering._image_encoder_extractor import (
    _ImageEncoderExtractor,
)
from pirn.domains.ml.types.data_split import DataSplit
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


class ImageEmbeddingExtractor(SubTapestry):
    """Append an image-column embedding feature to every split partition."""

    def __init__(
        self,
        *,
        split: Knot,
        image_column: str,
        image_encoder: ImageEncoderProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(split, Knot):
            raise TypeError("ImageEmbeddingExtractor: split must be a Knot")
        if not isinstance(image_column, str) or not image_column:
            raise ValueError(
                "ImageEmbeddingExtractor: image_column must be a non-empty "
                "string"
            )
        if not isinstance(image_encoder, ImageEncoderProvider):
            raise TypeError(
                "ImageEmbeddingExtractor: image_encoder must be an "
                "ImageEncoderProvider"
            )
        self._image_column = image_column
        self._image_encoder = image_encoder
        super().__init__(split=split, _config=_config, **kwargs)

    async def process(self, split: DataSplit, **_: Any) -> DataSplit:
        with Tapestry() as inner:
            split_node = _emit_value(
                value=split, _config=KnotConfig(id="split")
            )
            _ImageEncoderExtractor(
                split=split_node,
                image_column=self._image_column,
                image_encoder=self._image_encoder,
                _config=KnotConfig(id="encode"),
            )
        result = await self._run_inner(inner)
        encoded = result.outputs["encode"]
        if not isinstance(encoded, DataSplit):
            raise TypeError(
                "ImageEmbeddingExtractor: inner encoder did not return a "
                "DataSplit"
            )
        return encoded

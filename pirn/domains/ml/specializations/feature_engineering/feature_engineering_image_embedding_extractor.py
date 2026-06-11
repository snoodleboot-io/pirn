"""``FeatureEngineeringImageEmbeddingExtractor`` — append an image-column embedding feature
to every partition of a :class:`SplitManifest` via an
:class:`ImageEncoderProvider`.

Mirrors :class:`TextEmbeddingExtractor` but operates over image bytes
through an :class:`ImageEncoderProvider`.

Algorithm:
    1. Receive ``split`` (SplitManifest), ``image_column`` (str), and
       ``image_encoder`` (ImageEncoderProvider) via process().
    2. Validate image_column and image_encoder.
    3. Wire _ImageEncoderExtractor in an inner Tapestry.
    4. Run via _run_inner() and return the extended SplitManifest.


References:
    N/A — pirn-native implementation.
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
from pirn.domains.ml.types.split_manifest import SplitManifest
from pirn.nodes.sub_tapestry import SubTapestry


@knot
async def _emit_value(value: Any) -> Any:
    return value


class FeatureEngineeringImageEmbeddingExtractor(SubTapestry):
    """Append an image-column embedding feature to every split partition."""

    def __init__(
        self,
        *,
        split: Knot,
        image_column: Knot | str,
        image_encoder: Knot | ImageEncoderProvider,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            split=split,
            image_column=image_column,
            image_encoder=image_encoder,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        split: SplitManifest,
        image_column: str = "",
        image_encoder: ImageEncoderProvider | None = None,
        **_: Any,
    ) -> Any:
        """Encode the image column via the image encoder, append the embedding feature to each partition, and return the updated SplitManifest.

        Args:
            split: SplitManifest whose partitions receive the new image embedding feature.
            image_column: Non-empty name of the image column.
            image_encoder: ImageEncoderProvider to encode image bytes.

        Returns:
            SplitManifest with ``<image_column>_embedding`` appended to every partition's feature list.

        Raises:
            ValueError: If image_column is empty.
            TypeError: If image_encoder is not an ImageEncoderProvider or inner encoder fails.
        """
        if not isinstance(image_column, str) or not image_column:
            raise ValueError(
                "FeatureEngineeringImageEmbeddingExtractor: image_column must be a non-empty string"
            )
        if not isinstance(image_encoder, ImageEncoderProvider):
            raise TypeError(
                "FeatureEngineeringImageEmbeddingExtractor: image_encoder must be an ImageEncoderProvider"
            )
        split_node = _emit_value(value=split, _config=KnotConfig(id="split"))
        return _ImageEncoderExtractor(
            split=split_node,
            image_column=image_column,
            image_encoder=image_encoder,
            _config=KnotConfig(id="encode"),
        )

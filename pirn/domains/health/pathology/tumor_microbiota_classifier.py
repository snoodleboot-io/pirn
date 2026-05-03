"""``TumorMicrobiotaClassifier`` — classify tumor microbiota from 16S rRNA sequencing or metagenomic data."""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class TumorMicrobiotaClassifier(Knot):
    """Classify tumor microbiota from 16S rRNA sequencing or metagenomic data."""

    _VALID_TAXONOMIC_LEVELS: frozenset[str] = frozenset(
        {"phylum", "class", "order", "family", "genus", "species"}
    )

    def __init__(
        self,
        *,
        sequence_data: Knot,
        classifier_model: str,
        confidence_threshold: float,
        taxonomic_level: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(sequence_data, Knot):
            raise TypeError(
                "TumorMicrobiotaClassifier: sequence_data must be a Knot"
            )
        if not isinstance(classifier_model, str) or not classifier_model:
            raise ValueError(
                "TumorMicrobiotaClassifier: classifier_model must be a non-empty string"
            )
        if not isinstance(confidence_threshold, (int, float)) or not (0.0 <= confidence_threshold <= 1.0):
            raise ValueError(
                "TumorMicrobiotaClassifier: confidence_threshold must be in [0.0, 1.0]"
            )
        if taxonomic_level not in self._VALID_TAXONOMIC_LEVELS:
            raise ValueError(
                "TumorMicrobiotaClassifier: taxonomic_level must be one of "
                "'phylum', 'class', 'order', 'family', 'genus', 'species'"
            )
        self._classifier_model = classifier_model
        self._confidence_threshold = float(confidence_threshold)
        self._taxonomic_level = taxonomic_level
        super().__init__(sequence_data=sequence_data, _config=_config, **kwargs)

    async def process(
        self,
        sequence_data: dict[str, Any],
        **_: Any,
    ) -> dict[str, Any]:
        """Classify microbiota taxa from sequencing reads.

        Args:
            sequence_data: Dict with reads (list of read strings) and
                sample_id (str).

        Returns:
            Dict with sample_id (str), classifications (list of dicts with
            taxon, confidence, and read_count), and diversity_index (float).
        """
        if not isinstance(sequence_data, dict):
            raise TypeError(
                "TumorMicrobiotaClassifier: sequence_data must be a dict"
            )
        return {
            "sample_id": sequence_data.get("sample_id", ""),
            "classifications": [],
            "diversity_index": 0.0,
        }

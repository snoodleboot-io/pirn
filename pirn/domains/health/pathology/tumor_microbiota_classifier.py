"""``TumorMicrobiotaClassifier`` — classify tumor microbiota from sequencing data.

Algorithm:
    1. Validate classifier_model, confidence_threshold, and taxonomic_level.
    2. Assign taxonomic classifications to sequencing reads.
    3. Return per-sample classifications and diversity index.

Math:
    Shannon diversity index:

    $$H = -\\sum_{i} p_i \\ln p_i$$

    where p_i is the relative abundance of taxon i.

References:
    - Poore, G.D., et al. (2020). Microbiome analyses of blood and tissues suggest cancer diagnostic approach. Nature.
"""

from __future__ import annotations

import math
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig


class TumorMicrobiotaClassifier(Knot):
    """Classify tumor microbiota from 16S rRNA sequencing or metagenomic data."""

    def __init__(
        self,
        *,
        sequence_data: Knot | dict[str, Any],
        classifier_model: Knot | str,
        confidence_threshold: Knot | float,
        taxonomic_level: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            sequence_data=sequence_data,
            classifier_model=classifier_model,
            confidence_threshold=confidence_threshold,
            taxonomic_level=taxonomic_level,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        sequence_data: dict[str, Any],
        classifier_model: str,
        confidence_threshold: float,
        taxonomic_level: str,
        **_: Any,
    ) -> dict[str, Any]:
        """Classify microbiota taxa from sequencing reads.

        Args:
            sequence_data: Dict with reads (list of read strings) and sample_id (str).
            classifier_model: Name of the classifier model to use.
            confidence_threshold: Minimum classification confidence in [0.0, 1.0].
            taxonomic_level: One of 'phylum', 'class', 'order', 'family', 'genus', 'species'.

        Returns:
            Dict with sample_id (str), classifications (list of dicts with
            taxon, confidence, and read_count), and diversity_index (float).

        Raises:
            TypeError: If sequence_data is not a dict.
            ValueError: If classifier_model is empty, confidence_threshold is out of range,
                or taxonomic_level is invalid.
        """
        if not isinstance(sequence_data, dict):
            raise TypeError("TumorMicrobiotaClassifier: sequence_data must be a dict")
        if not isinstance(classifier_model, str) or not classifier_model:
            raise ValueError(
                "TumorMicrobiotaClassifier: classifier_model must be a non-empty string"
            )
        if not isinstance(confidence_threshold, (int, float)) or not (
            0.0 <= float(confidence_threshold) <= 1.0
        ):
            raise ValueError(
                "TumorMicrobiotaClassifier: confidence_threshold must be in [0.0, 1.0]"
            )
        valid_taxonomic_levels = frozenset(
            {"phylum", "class", "order", "family", "genus", "species"}
        )
        if taxonomic_level not in valid_taxonomic_levels:
            raise ValueError(
                "TumorMicrobiotaClassifier: taxonomic_level must be one of "
                "'phylum', 'class', 'order', 'family', 'genus', 'species'"
            )
        taxa_abundances: dict = sequence_data.get(
            "taxa_abundances", sequence_data.get("abundances", {})
        )
        total_reads = sum(
            v for v in taxa_abundances.values() if isinstance(v, (int, float)) and v > 0
        )
        if not total_reads:
            return {
                "sample_id": sequence_data.get("sample_id", ""),
                "classifications": [],
                "diversity_index": 0.0,
            }
        rel_abunds = {
            k: v / total_reads
            for k, v in taxa_abundances.items()
            if isinstance(v, (int, float)) and v > 0
        }
        filtered = {k: v for k, v in rel_abunds.items() if v >= confidence_threshold}
        H = -sum(p * math.log(p) for p in filtered.values() if p > 0)
        classifications = [
            {"taxon": k, "confidence": v, "read_count": int(v * total_reads)}
            for k, v in sorted(filtered.items(), key=lambda x: -x[1])
        ]
        return {
            "sample_id": sequence_data.get("sample_id", ""),
            "classifications": classifications,
            "diversity_index": H,
        }

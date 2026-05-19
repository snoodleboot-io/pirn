"""``MedicationReconciliationPipeline`` — ingest → normalise → dedup pipeline.

Composed pipeline: :class:`RxNormNormalizer` resolves drug names to
RxCUI, then a final dedup step collapses duplicates. The pipeline is
expressed as a :class:`SubTapestry` so its inner graph is visible to
the engine and can be cached / replayed independently.

Algorithm:
    1. Receive a sequence of drug name strings and a drug-name-to-RxCUI mapping.
    2. Validate that drug_names is a list/tuple of strings and mapping is a Mapping.
    3. Normalise each drug name to an RxCUI via RxNormNormalizer.
    4. Deduplicate the RxCUI codes via _DedupRxCUIs.
    5. Return the inner RunResult.


References:
    - RxNorm: https://www.nlm.nih.gov/research/umls/rxnorm/
    - NLM RxNorm API: https://lhncbc.nlm.nih.gov/RxNav/APIs/RxNormAPIs.html
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.health.clinical._dedup_rx_cuis import _DedupRxCUIs
from pirn.domains.health.clinical.rxnorm_normalizer import RxNormNormalizer
from pirn.nodes.sub_tapestry import SubTapestry


class MedicationReconciliationPipeline(SubTapestry):
    """Normalise a list of drug names and emit a deduplicated RxCUI tuple."""

    def __init__(
        self,
        *,
        drug_names: Knot | Sequence[str],
        mapping: Knot | Mapping[str, str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            drug_names=drug_names,
            mapping=mapping,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        drug_names: Sequence[str],
        mapping: Mapping[str, str],
        **_: Any,
    ) -> Any:
        """Normalise drug names to RxCUI codes, deduplicate them, and return the terminal Knot.

        Args:
            drug_names: Sequence of drug name strings to normalise.
            mapping: Mapping of drug name to RxCUI code string.

        Returns:
            A RunResult summarising the outcome of the inner tapestry execution.

        Raises:
            TypeError: If drug_names is not a list/tuple or mapping is not a Mapping.
        """
        if not isinstance(drug_names, (list, tuple)):
            raise TypeError("MedicationReconciliationPipeline: drug_names must be list/tuple")
        if not isinstance(mapping, Mapping):
            raise TypeError("MedicationReconciliationPipeline: mapping must be a Mapping")
        normalised = RxNormNormalizer(
            drug_names=tuple(drug_names),
            mapping=mapping,
            _config=KnotConfig(id="rxnorm-normalize"),
        )
        return _DedupRxCUIs(
            rxcuis=normalised,
            _config=KnotConfig(id="rxnorm-dedup"),
        )

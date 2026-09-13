"""``ChampionChallengerGate`` — deprecated alias for :class:`ChampionChallengerCheck`.

Kept for one deprecation cycle so existing pipelines that reference the old
``*Gate`` name keep working (R9 renamed assessment knots from ``*Gate`` to
``*Check`` — see ``docs/contributing/knot-design-rules.md`` Rule 7).
Construction emits a ``DeprecationWarning``; behaviour is otherwise
identical to :class:`ChampionChallengerCheck`, which this class subclasses
without overriding ``process()``.

References:
    N/A — pirn-native implementation.
"""

from __future__ import annotations

import warnings
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_ml.specializations.experiments.champion_challenger_check import (
    ChampionChallengerCheck,
)


class ChampionChallengerGate(ChampionChallengerCheck):
    """Deprecated alias — use :class:`ChampionChallengerCheck` instead."""

    def __init__(
        self,
        *,
        champion: Knot,
        challenger: Knot,
        split: Knot,
        primary_metric: Knot | str,
        min_improvement: Knot | float = 0.0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        warnings.warn(
            "ChampionChallengerGate is deprecated; use ChampionChallengerCheck instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(
            champion=champion,
            challenger=challenger,
            split=split,
            primary_metric=primary_metric,
            min_improvement=min_improvement,
            _config=_config,
            **kwargs,
        )

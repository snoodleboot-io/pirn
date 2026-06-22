"""``FuzzyDeduplicator`` — multi-stage fuzzy record matching.

Pipeline stages
---------------
1. **Tokenizer** — normalises a blocking key field to a token.
2. **CandidatePairGenerator** — emits (left_idx, right_idx) pairs that
   share a blocking token (avoids O(n²) comparison).
3. **SimilarityScorer** — computes a similarity score for each pair using
   either Levenshtein edit-distance or Jaro-Winkler.
4. **ClusterAssigner** — groups records above the threshold into a cluster
   and keeps only the cluster representative (first record by index).

Algorithm:
    1. Receive resolved ``rows``, ``match_column``, ``blocking_key_length``,
       ``similarity_metric``, and ``threshold`` in ``process()``.
    2. Validate all inputs: identifier safety, metric name, threshold range,
       and blocking key length.
    3. Build a blocking index: group row indices by the first
       ``blocking_key_length`` characters of their normalised match value.
    4. For each pair of indices in the same block, score similarity.
    5. Merge pairs above ``threshold`` into clusters via union-find
       (root = min index).
    6. Emit the first row (lowest original index) of each cluster.

Math:
    Jaro similarity:
    $J(a,b) = \\frac{1}{3}\\left(\\frac{m}{|a|}+\\frac{m}{|b|}+\\frac{m-t/2}{m}\\right)$
    where $m$ = matching characters, $t$ = transpositions.

    Jaro-Winkler: $JW = J + p \\cdot l \\cdot (1 - J)$
    where $l$ = common prefix length (max 4), $p = 0.1$.

    Levenshtein similarity: $1 - \\frac{\\text{edit\\_distance}(a,b)}{\\max(|a|,|b|)}$

References:
    [1] Jaro, M.A. (1989). *Advances in Record-Linkage Methodology*.
        JASA 84(406):414-420.
    [2] Winkler, W.E. (1990). *String Comparator Metrics and Enhanced Decision Rules*.
        ASA Proceedings of the Section on Survey Research Methods.
    [3] pirn — IdentifierValidator:
        pirn_data/identifier_validator.py
"""

from __future__ import annotations

from typing import Any, Literal

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.identifier_validator import IdentifierValidator


class FuzzyDeduplicator(Knot):
    """Deduplicate records using fuzzy string similarity with candidate blocking."""

    def __init__(
        self,
        *,
        rows: Knot,
        match_column: Knot | str,
        blocking_key_length: Knot | int,
        similarity_metric: Knot | Literal["levenshtein", "jaro_winkler"],
        threshold: Knot | float,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            rows=rows,
            match_column=match_column,
            blocking_key_length=blocking_key_length,
            similarity_metric=similarity_metric,
            threshold=threshold,
            _config=_config,
            **kwargs,
        )

    @staticmethod
    def _levenshtein(str_a: str, str_b: str) -> float:
        if str_a == str_b:
            return 1.0
        la, lb = len(str_a), len(str_b)
        if la == 0 or lb == 0:
            return 0.0
        prev = list(range(lb + 1))
        for row_idx, char_a in enumerate(str_a, 1):
            curr = [row_idx] + [0] * lb
            for col_idx, char_b in enumerate(str_b, 1):
                curr[col_idx] = min(
                    prev[col_idx] + 1,
                    curr[col_idx - 1] + 1,
                    prev[col_idx - 1] + (0 if char_a == char_b else 1),
                )
            prev = curr
        return 1.0 - prev[lb] / max(la, lb)

    @staticmethod
    def _jaro_winkler(str_a: str, str_b: str) -> float:
        if str_a == str_b:
            return 1.0
        la, lb = len(str_a), len(str_b)
        if la == 0 or lb == 0:
            return 0.0
        match_dist = max(0, max(la, lb) // 2 - 1)
        a_flags = [False] * la
        b_flags = [False] * lb
        matches = 0
        for pos_a in range(la):
            start = max(0, pos_a - match_dist)
            end = min(pos_a + match_dist + 1, lb)
            for pos_b in range(start, end):
                if b_flags[pos_b] or str_a[pos_a] != str_b[pos_b]:
                    continue
                a_flags[pos_a] = True
                b_flags[pos_b] = True
                matches += 1
                break
        if matches == 0:
            return 0.0
        a_match = [str_a[pos_a] for pos_a in range(la) if a_flags[pos_a]]
        b_match = [str_b[pos_b] for pos_b in range(lb) if b_flags[pos_b]]
        transpositions = sum(
            1 for char_a, char_b in zip(a_match, b_match, strict=False) if char_a != char_b
        )
        jaro = (matches / la + matches / lb + (matches - transpositions / 2) / matches) / 3.0
        prefix = 0
        for prefix_idx in range(min(4, la, lb)):
            if str_a[prefix_idx] == str_b[prefix_idx]:
                prefix += 1
            else:
                break
        return jaro + prefix * 0.1 * (1.0 - jaro)

    @staticmethod
    def _score(metric: str, str_a: str, str_b: str) -> float:
        if metric == "levenshtein":
            return FuzzyDeduplicator._levenshtein(str_a, str_b)
        return FuzzyDeduplicator._jaro_winkler(str_a, str_b)

    async def process(
        self,
        *,
        rows: Any,
        match_column: Any,
        blocking_key_length: Any,
        similarity_metric: Any,
        threshold: Any,
        **_: Any,
    ) -> list[dict[str, Any]]:
        if not isinstance(match_column, str) or not match_column:
            raise ValueError("FuzzyDeduplicator: match_column must be a non-empty string")
        IdentifierValidator.validate_column("match_column", match_column)
        if not isinstance(blocking_key_length, int) or blocking_key_length < 1:
            raise ValueError("FuzzyDeduplicator: blocking_key_length must be a positive integer")
        if similarity_metric not in ("levenshtein", "jaro_winkler"):
            raise ValueError(
                "FuzzyDeduplicator: similarity_metric must be 'levenshtein' or 'jaro_winkler'"
            )
        if not (0.0 < threshold <= 1.0):
            raise ValueError("FuzzyDeduplicator: threshold must be in (0, 1]")
        tokens: list[str] = [str(r.get(match_column, "")).lower() for r in rows]
        blocks: dict[str, list[int]] = {}
        for idx, token in enumerate(tokens):
            key = token[:blocking_key_length]
            blocks.setdefault(key, []).append(idx)

        cluster_of: dict[int, int] = {}
        for indices in blocks.values():
            for i_pos in range(len(indices)):
                for j_pos in range(i_pos + 1, len(indices)):
                    idx_left, idx_right = indices[i_pos], indices[j_pos]
                    score = FuzzyDeduplicator._score(
                        similarity_metric, tokens[idx_left], tokens[idx_right]
                    )
                    if score >= threshold:
                        root_i = cluster_of.get(idx_left, idx_left)
                        root_j = cluster_of.get(idx_right, idx_right)
                        merged = min(root_i, root_j)
                        cluster_of[idx_left] = merged
                        cluster_of[idx_right] = merged
                        for member_idx, member_cluster in cluster_of.items():
                            if member_cluster == max(root_i, root_j):
                                cluster_of[member_idx] = merged

        seen_clusters: set[int] = set()
        result: list[dict[str, Any]] = []
        for idx, row in enumerate(rows):
            cluster = cluster_of.get(idx, idx)
            if cluster not in seen_clusters:
                seen_clusters.add(cluster)
                result.append(row)
        return result

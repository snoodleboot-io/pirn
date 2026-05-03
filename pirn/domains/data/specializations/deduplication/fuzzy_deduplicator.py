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

The knot accepts a list of dicts and returns the deduplicated list.
"""

from __future__ import annotations

from typing import Any, Literal, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.identifier_validator import IdentifierValidator


def _levenshtein(a: str, b: str) -> float:
    """Return normalised similarity in [0, 1] via Levenshtein distance."""
    if a == b:
        return 1.0
    la, lb = len(a), len(b)
    if la == 0 or lb == 0:
        return 0.0
    prev = list(range(lb + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * lb
        for j, cb in enumerate(b, 1):
            curr[j] = min(
                prev[j] + 1,
                curr[j - 1] + 1,
                prev[j - 1] + (0 if ca == cb else 1),
            )
        prev = curr
    return 1.0 - prev[lb] / max(la, lb)


def _jaro_winkler(a: str, b: str) -> float:
    """Return Jaro-Winkler similarity in [0, 1]."""
    if a == b:
        return 1.0
    la, lb = len(a), len(b)
    if la == 0 or lb == 0:
        return 0.0
    match_dist = max(la, lb) // 2 - 1
    if match_dist < 0:
        match_dist = 0
    a_flags = [False] * la
    b_flags = [False] * lb
    matches = 0
    transpositions = 0
    for i in range(la):
        start = max(0, i - match_dist)
        end = min(i + match_dist + 1, lb)
        for j in range(start, end):
            if b_flags[j] or a[i] != b[j]:
                continue
            a_flags[i] = True
            b_flags[j] = True
            matches += 1
            break
    if matches == 0:
        return 0.0
    a_match = [a[i] for i in range(la) if a_flags[i]]
    b_match = [b[j] for j in range(lb) if b_flags[j]]
    for i in range(len(a_match)):
        if a_match[i] != b_match[i]:
            transpositions += 1
    jaro = (
        matches / la + matches / lb + (matches - transpositions / 2) / matches
    ) / 3.0
    prefix = 0
    for i in range(min(4, la, lb)):
        if a[i] == b[i]:
            prefix += 1
        else:
            break
    return jaro + prefix * 0.1 * (1.0 - jaro)


class FuzzyDeduplicator(Knot):
    """Deduplicate records using fuzzy string similarity with candidate blocking."""

    def __init__(
        self,
        *,
        rows: Knot,
        match_column: str,
        blocking_key_length: int = 3,
        similarity_metric: Literal["levenshtein", "jaro_winkler"] = "jaro_winkler",
        threshold: float = 0.85,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        IdentifierValidator.validate_column("match_column", match_column)
        if not isinstance(blocking_key_length, int) or blocking_key_length < 1:
            raise ValueError(
                "FuzzyDeduplicator: blocking_key_length must be a positive integer"
            )
        if similarity_metric not in ("levenshtein", "jaro_winkler"):
            raise ValueError(
                "FuzzyDeduplicator: similarity_metric must be 'levenshtein' or 'jaro_winkler'"
            )
        if not (0.0 < threshold <= 1.0):
            raise ValueError(
                "FuzzyDeduplicator: threshold must be in (0, 1]"
            )
        self._match_column = match_column
        self._blocking_key_length = blocking_key_length
        self._similarity_metric = similarity_metric
        self._threshold = threshold
        super().__init__(rows=rows, _config=_config, **kwargs)

    def _score(self, a: str, b: str) -> float:
        if self._similarity_metric == "levenshtein":
            return _levenshtein(a, b)
        return _jaro_winkler(a, b)

    async def process(
        self, rows: list[dict[str, Any]], **_: Any
    ) -> list[dict[str, Any]]:
        """Apply blocking + fuzzy scoring to deduplicate rows by match_column.

        Records are clustered by similarity; only the first record (lowest
        original index) from each cluster is retained.

        Args:
            rows: Upstream rows as a list of dicts.

        Returns:
            Deduplicated list with one representative per fuzzy-match cluster.
        """
        tokens: list[str] = [
            str(r.get(self._match_column, "")).lower() for r in rows
        ]
        blocks: dict[str, list[int]] = {}
        for idx, token in enumerate(tokens):
            key = token[: self._blocking_key_length]
            blocks.setdefault(key, []).append(idx)

        cluster_of: dict[int, int] = {}
        for indices in blocks.values():
            for i_pos in range(len(indices)):
                for j_pos in range(i_pos + 1, len(indices)):
                    i, j = indices[i_pos], indices[j_pos]
                    score = self._score(tokens[i], tokens[j])
                    if score >= self._threshold:
                        root_i = cluster_of.get(i, i)
                        root_j = cluster_of.get(j, j)
                        merged = min(root_i, root_j)
                        cluster_of[i] = merged
                        cluster_of[j] = merged
                        for k, v in cluster_of.items():
                            if v == max(root_i, root_j):
                                cluster_of[k] = merged

        seen_clusters: set[int] = set()
        result: list[dict[str, Any]] = []
        for idx, row in enumerate(rows):
            cluster = cluster_of.get(idx, idx)
            if cluster not in seen_clusters:
                seen_clusters.add(cluster)
                result.append(row)
        return result

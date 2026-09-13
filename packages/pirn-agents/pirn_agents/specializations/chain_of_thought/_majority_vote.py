"""``_MajorityVote`` — Reduce ``combine`` target for self-consistency."""

from __future__ import annotations

from collections import Counter


class _MajorityVote:
    """Reduce ``combine`` target: case-insensitive majority vote over samples."""

    @staticmethod
    def combine(answers: list[str]) -> str:
        """Return the majority-vote answer, original casing, first on ties.

        Args:
            answers: The sampled answer strings.

        Returns:
            The most common stripped answer, in its first-encountered original
            casing.

        Math:
            Given normalised answers :math:`a_1, \\ldots, a_n` (stripped,
            lower-cased), the winner is
            :math:`\\arg\\max_{v} \\lvert \\{ i : a_i = v \\} \\rvert`, ties
            broken by first occurrence.
        """
        normalised = [a.strip().lower() for a in answers]
        counts: Counter[str] = Counter(normalised)
        top_normal = counts.most_common(1)[0][0]
        for original, norm in zip(answers, normalised, strict=False):
            if norm == top_normal:
                return original.strip()
        return answers[0].strip()

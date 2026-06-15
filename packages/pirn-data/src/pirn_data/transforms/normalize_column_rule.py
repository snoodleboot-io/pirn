"""``NormalizeColumnRule`` — per-column rule consumed by
:class:`pirn_data.transforms.normalize.Normalize`.

Three rule families are supported (each opt-in per column):

- **strip_whitespace**: leading/trailing whitespace removed; runs of
  internal whitespace collapsed to a single space.
- **case**: ``"lower"``, ``"upper"``, ``"title"``, or ``None`` (no change).
- **null_tokens**: a tuple of strings to treat as ``None`` after stripping
  (e.g. ``("", "NA", "n/a", "null")``). Comparison is case-insensitive
  unless ``null_tokens_case_sensitive=True``.

Defaults perform no transformation; set the fields you want to apply.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizeColumnRule:
    """Per-column normalisation rule."""

    strip_whitespace: bool = False
    case: str | None = None
    null_tokens: tuple[str, ...] = ()
    null_tokens_case_sensitive: bool = False

    def __post_init__(self) -> None:
        allowed = ("lower", "upper", "title")
        if self.case is not None and self.case not in allowed:
            raise ValueError(
                f"NormalizeColumnRule.case must be one of "
                f"{list(allowed)} or None, got {self.case!r}"
            )

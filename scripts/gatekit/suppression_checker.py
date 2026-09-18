"""``SuppressionChecker`` — every suppression names a real rule and says why.

Rules
-----
``suppression_without_rule_or_reason``
    A suppression comment that does not name its rule, or carries no real reason:

    * ``# type: ignore`` in any form — pyright treats the bracket of a
      ``type: ignore[...]`` as decoration and suppresses *every* rule on the line;
      write ``# pyright: ignore[<rule>]  # <reason>``;
    * ``# pyright: ignore`` without a bracketed rule list;
    * ``# noqa`` without codes;
    * any ``pyright: ignore[...]``, ``noqa: <codes>`` or ``pragma: no cover`` without a
      reason of at least three words — after the directive on the same comment
      (``# noqa: BLE001 — surface the import failure``) or as a following
      ``# <reason>`` segment. ``# .`` and ``# x`` are not reasons.

``suppression_unknown_rule``
    A pyright rule or ruff code the pinned tool does not define
    (``ignore[notARealRule]``, ``noqa: XYZ999``), read from
    :class:`~gatekit.suppression_rule_catalog.SuppressionRuleCatalog`.

``file_level_directive``
    A file-wide switch: any ``# pyright: <setting>`` other than a per-line ``ignore``,
    ``# ruff: noqa``, ``# flake8: noqa``, ``# mypy: ...``. Checker settings live in the
    package's configuration, never in a file.

Only comment tokens are read, so directive-like text inside a string is never a finding.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import ClassVar

from gatekit.source_file import SourceFile
from gatekit.suppression_rule_catalog import SuppressionRuleCatalog
from gatekit.violation import Violation


class SuppressionChecker:
    """Validates ``type:``/``pyright:``/``noqa``/``pragma`` comments against the catalog."""

    _type_ignore: ClassVar[re.Pattern[str]] = re.compile(r"^type\s*:\s*ignore\b")
    _pyright_ignore: ClassVar[re.Pattern[str]] = re.compile(
        r"^pyright\s*:\s*ignore\b(?:\[(?P<rules>[^\]]*)\])?(?P<rest>.*)$"
    )
    _pyright_directive: ClassVar[re.Pattern[str]] = re.compile(r"^pyright\s*:")
    _file_noqa: ClassVar[re.Pattern[str]] = re.compile(
        r"^(?:ruff|flake8)\s*:\s*noqa\b|^mypy\s*:", re.IGNORECASE
    )
    _noqa: ClassVar[re.Pattern[str]] = re.compile(
        r"^noqa\b(?:\s*:\s*(?P<codes>[A-Z]+[0-9]+(?:[\s,]+[A-Z]+[0-9]+)*))?(?P<rest>.*)$",
        re.IGNORECASE,
    )
    _pragma: ClassVar[re.Pattern[str]] = re.compile(
        r"^pragma\s*:\s*no\s*(?:cover|branch)\b(?P<rest>.*)$"
    )
    _word: ClassVar[re.Pattern[str]] = re.compile(r"[A-Za-z]{2,}")
    _minimum_reason_words: ClassVar[int] = 3

    def __init__(self, catalog: SuppressionRuleCatalog) -> None:
        self._catalog = catalog

    @classmethod
    def is_reason(cls, text: str) -> bool:
        return len(cls._word.findall(text)) >= cls._minimum_reason_words

    def check(self, source_file: SourceFile) -> list[Violation]:
        violations: list[Violation] = []
        for lineno, _col, comment in source_file.comments:
            segments = [segment.strip() for segment in comment.split("#")[1:]]
            for index, segment in enumerate(segments):
                trailing = " ".join(
                    s for s in segments[index + 1 :] if not self._is_directive(s)
                )
                violations.extend(
                    self._check_segment(source_file, lineno, comment, segment, trailing)
                )
        return violations

    def _is_directive(self, segment: str) -> bool:
        return bool(
            self._type_ignore.match(segment)
            or self._pyright_directive.match(segment)
            or self._file_noqa.match(segment)
            or self._noqa.match(segment)
            or self._pragma.match(segment)
        )

    def _check_segment(
        self,
        source_file: SourceFile,
        lineno: int,
        comment: str,
        segment: str,
        trailing: str,
    ) -> list[Violation]:
        path = source_file.path
        shown = comment.strip()
        if self._type_ignore.match(segment):
            return [
                Violation(
                    "suppression_without_rule_or_reason",
                    path,
                    lineno,
                    f"{shown!r} — pyright ignores the rule list of a 'type: ignore' and "
                    "suppresses everything; write '# pyright: ignore[<rule>]  # <reason>'",
                )
            ]
        pyright = self._pyright_ignore.match(segment)
        if pyright is not None:
            rules = [r.strip() for r in (pyright.group("rules") or "").split(",") if r.strip()]
            return self._named_and_reasoned(
                path, lineno, shown, rules, self._catalog.pyright_rules,
                f"{pyright.group('rest')} {trailing}", "pyright rule",
            )
        if self._pyright_directive.match(segment) or self._file_noqa.match(segment):
            return [
                Violation(
                    "file_level_directive",
                    path,
                    lineno,
                    f"{shown!r} — checker settings live in the package configuration, "
                    "not in a file",
                )
            ]
        noqa = self._noqa.match(segment)
        if noqa is not None:
            codes = re.split(r"[\s,]+", noqa.group("codes") or "")
            return self._named_and_reasoned(
                path, lineno, shown, [c for c in codes if c], self._catalog.ruff_codes,
                f"{noqa.group('rest')} {trailing}", "ruff code",
            )
        pragma = self._pragma.match(segment)
        if pragma is not None and not self.is_reason(f"{pragma.group('rest')} {trailing}"):
            return [
                Violation(
                    "suppression_without_rule_or_reason",
                    path,
                    lineno,
                    f"{shown!r} — a coverage pragma carries a reason of at least three words",
                )
            ]
        return []

    def _named_and_reasoned(
        self,
        path: Path,
        lineno: int,
        shown: str,
        names: list[str],
        known: frozenset[str],
        reason: str,
        kind: str,
    ) -> list[Violation]:
        violations: list[Violation] = []
        if not names:
            violations.append(
                Violation(
                    "suppression_without_rule_or_reason",
                    path,
                    lineno,
                    f"{shown!r} — a suppression names the {kind} it suppresses",
                )
            )
        unknown = [name for name in names if name not in known]
        if unknown:
            violations.append(
                Violation(
                    "suppression_unknown_rule",
                    path,
                    lineno,
                    f"{shown!r} — unknown {kind}(s) {unknown}: the suppression suppresses "
                    "nothing the tool reports",
                )
            )
        if not self.is_reason(reason):
            violations.append(
                Violation(
                    "suppression_without_rule_or_reason",
                    path,
                    lineno,
                    f"{shown!r} — a suppression carries a reason of at least three words",
                )
            )
        return violations

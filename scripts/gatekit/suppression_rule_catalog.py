"""``SuppressionRuleCatalog`` — the rule names a suppression comment may name.

A ``# pyright: ignore[notARealRule]`` or ``# noqa: XYZ999`` suppresses nothing the
tool knows about, yet reads like a justified exception. The catalog is read from the
pinned tools themselves, never from a hand list that drifts:

* pyright diagnostic rules — the ``DiagnosticRule`` enum compiled into the installed
  ``pyright`` package's ``pyright-internal.js`` (``n.reportFoo="reportFoo"``);
* ruff rule codes — ``ruff rule --all --output-format json``.

Either tool missing is an unusable invocation, not a pass.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import ClassVar


class SuppressionRuleCatalog:
    """The pyright rule names and ruff codes known to the pinned linters."""

    _pyright_rule: ClassVar[re.Pattern[str]] = re.compile(r"\.(report[A-Z][A-Za-z]+)=\"\1\"")

    def __init__(self, pyright_rules: frozenset[str], ruff_codes: frozenset[str]) -> None:
        if not pyright_rules or not ruff_codes:
            raise LookupError("the suppression rule catalog is empty")
        self.pyright_rules = pyright_rules
        self.ruff_codes = ruff_codes

    @classmethod
    def from_installed_tools(cls, ruff: str | None = None) -> SuppressionRuleCatalog:
        """Read both catalogs from the installed ``pyright`` package and ``ruff`` binary."""
        return cls(cls.installed_pyright_rules(), cls.installed_ruff_codes(ruff))

    @classmethod
    def installed_pyright_rules(cls) -> frozenset[str]:
        spec = importlib.util.find_spec("pyright")
        if spec is None or spec.origin is None:
            raise LookupError(
                "the pyright package is not installed — install the pinned pyright "
                "to validate '# pyright: ignore[...]' rule names"
            )
        bundles = sorted(Path(spec.origin).parent.rglob("pyright-internal.js"))
        if not bundles:
            # Wheels that do not bundle the npm package download it on first run.
            version = importlib.metadata.version("pyright")
            cache = Path.home() / ".cache" / "pyright-python" / version
            bundles = sorted(cache.glob("node_modules/pyright/dist/pyright-internal.js"))
        if not bundles:
            raise LookupError(
                f"no pyright-internal.js under {Path(spec.origin).parent} or the "
                "pyright-python cache (run `pyright --version` once) — cannot read "
                "pyright's diagnostic rule names"
            )
        rules = set(cls._pyright_rule.findall(bundles[0].read_text(encoding="utf-8")))
        if not rules:
            raise LookupError(f"no DiagnosticRule names found in {bundles[0]}")
        return frozenset(rules)

    @staticmethod
    def installed_ruff_codes(ruff: str | None = None) -> frozenset[str]:
        executable = ruff or shutil.which("ruff")
        if executable is None:
            raise LookupError(
                "ruff is not on PATH — install the pinned ruff to validate "
                "'# noqa: <code>' rule codes"
            )
        completed = subprocess.run(
            [executable, "rule", "--all", "--output-format", "json"],
            capture_output=True,
            text=True,
            check=True,
        )
        rules = json.loads(completed.stdout)
        return frozenset(str(rule["code"]) for rule in rules)

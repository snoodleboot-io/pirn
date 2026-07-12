"""``PromptTemplate`` — a typed, versioned prompt template with safe rendering.

A template pairs a ``(name, version)`` identity with a body containing
``{{ variable }}`` slots and ``{{> partial }}`` includes. Rendering is
**injection-safe by construction**:

* No code is ever executed — there is no ``eval`` and no ``str.format`` (whose
  ``{obj.__class__}`` style access can traverse into arbitrary attributes).
  Substitution is a single left-to-right regex pass over a whitelist of
  ``[A-Za-z_][A-Za-z0-9_]*`` placeholder names only.
* Because substitution never re-scans the text it inserts, a value that itself
  contains ``{{ ... }}`` is inert and cannot inject a new slot — the classic
  prompt-injection-via-variable vector is closed.
* Partials expand exactly one level, so a partial cannot recursively pull in
  further partials (no expansion loops).

This mirrors the guard style used by the calculator / format tools: a strict
whitelist plus literal, single-pass substitution rather than an interpreter.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.prompt.prompt_render_error import PromptRenderError


def _placeholder_finditer(text: str) -> list[re.Match[str]]:
    """Return every ``{{ name }}`` / ``{{> name }}`` match in ``text``.

    Group 1 is ``">"`` for a partial include (empty for a variable slot); group
    2 is the whitelisted name.
    """
    return list(re.finditer(r"\{\{\s*(>?)\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}", text))


@dataclass(frozen=True)
class PromptTemplate(PirnOpaqueValue):
    """A versioned prompt template with variable slots and partial includes.

    Attributes
    ----------
    name:
        Registry name of the template (e.g. ``"summarize"``).
    version:
        Dotted version string (e.g. ``"1.0.0"``); ordered numerically by the
        registry so ``"1.10.0"`` is newer than ``"1.9.0"``.
    template:
        The body, with ``{{ variable }}`` slots and ``{{> partial }}`` includes.
    partials:
        Named fragments inlined for ``{{> name }}`` includes.
    description:
        Optional human-readable summary used by authoring docs / tooling.
    """

    name: str
    version: str
    template: str
    partials: Mapping[str, str] = field(default_factory=dict)
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise TypeError("PromptTemplate: name must be a non-empty str")
        if not isinstance(self.version, str) or not self.version:
            raise TypeError("PromptTemplate: version must be a non-empty str")
        if not isinstance(self.template, str):
            raise TypeError(
                f"PromptTemplate: template must be a str, got {type(self.template).__name__}"
            )
        if not isinstance(self.partials, Mapping):
            raise TypeError("PromptTemplate: partials must be a mapping of str -> str")
        for key, value in self.partials.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise TypeError("PromptTemplate: partials must map str names to str bodies")

    def variable_names(self) -> tuple[str, ...]:
        """Return the sorted, unique variable names across body and partials.

        This is the full set a caller must supply to render the template in
        strict mode (slots referenced directly plus those inside any partial
        that the body includes).
        """
        names: set[str] = set()
        for source in (self.template, *self.partials.values()):
            for match in _placeholder_finditer(source):
                if not match.group(1):
                    names.add(match.group(2))
        return tuple(sorted(names))

    def partial_names(self) -> tuple[str, ...]:
        """Return the sorted, unique partial names the body includes."""
        names = {m.group(2) for m in _placeholder_finditer(self.template) if m.group(1)}
        return tuple(sorted(names))

    def render(self, variables: Mapping[str, Any] | None = None, *, strict: bool = True) -> str:
        """Render the template by substituting ``variables`` into its slots.

        Args:
            variables: Values keyed by slot name. In strict mode every slot must
                be supplied and each value must be a ``str``/``int``/``float``/
                ``bool``/``None`` (``None`` renders as empty); extra keys are
                ignored.
            strict: When ``True`` (default), missing slots, unresolved
                placeholders, unknown partials, and non-primitive values raise
                :class:`PromptRenderError`. When ``False``, unknown variable
                slots are left untouched and unknown partials expand to ``""``.

        Returns:
            The rendered prompt text.

        Raises:
            PromptRenderError: On any strict-mode safety or completeness failure.
        """
        values = dict(variables) if variables is not None else {}
        if strict:
            self._validate_values(values)
        expanded = self._expand_partials(self.template, strict=strict)
        return self._substitute(expanded, values, strict=strict)

    def _validate_values(self, values: Mapping[str, Any]) -> None:
        """Reject non-primitive values so no arbitrary object is stringified."""
        for key, value in values.items():
            if value is not None and not isinstance(value, (str, int, float, bool)):
                raise PromptRenderError(
                    f"PromptTemplate {self.name!r}: value for {key!r} must be a "
                    f"str/int/float/bool/None, got {type(value).__name__}"
                )

    def _expand_partials(self, text: str, *, strict: bool) -> str:
        """Inline ``{{> name }}`` includes exactly one level deep."""

        def _replace(match: re.Match[str]) -> str:
            if not match.group(1):
                return match.group(0)
            name = match.group(2)
            if name in self.partials:
                return self.partials[name]
            if strict:
                raise PromptRenderError(f"PromptTemplate {self.name!r}: unknown partial {name!r}")
            return ""

        return re.sub(r"\{\{\s*(>?)\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}", _replace, text)

    def _substitute(self, text: str, values: Mapping[str, Any], *, strict: bool) -> str:
        """Substitute variable slots in a single, non-recursive left-to-right pass."""

        def _replace(match: re.Match[str]) -> str:
            if match.group(1):
                # A leftover partial token (e.g. nested inside a partial body).
                if strict:
                    raise PromptRenderError(
                        f"PromptTemplate {self.name!r}: unresolved partial {match.group(2)!r}"
                    )
                return ""
            name = match.group(2)
            if name in values:
                value = values[name]
                return "" if value is None else str(value)
            if strict:
                raise PromptRenderError(f"PromptTemplate {self.name!r}: missing variable {name!r}")
            return match.group(0)

        return re.sub(r"\{\{\s*(>?)\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}", _replace, text)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "template": self.template,
            "partials": dict(self.partials),
            "description": self.description,
        }

"""``AgentKnotIdFactory`` — deterministic, stable knot ids for built agents.

The high-level builder must attach a :class:`~pirn.core.knot_config.KnotConfig`
``id`` to the top-level :class:`~pirn.nodes.sub_tapestry.SubTapestry` it
generates. Ids are derived purely from the *structure* of the request — the
pattern, provider/tool references, and options — never from wall-clock time or
randomness, so building the same spec twice yields the same id. Stable ids keep
lineage records human-readable and reproducible across runs, and let generated
graphs share the engine's content-addressed cache exactly like hand-wired ones.

ADR agents-speaks-core WS2 part 2 - breaking id-format change, sanctioned:
:meth:`derive` now digests the structural signature via
:func:`pirn.core.hashing.content_hash` (``strict=True``) instead of
the former ``CanonicalJson`` (deleted, PIR-872). The
signature is always plain JSON-safe data (strings, lists, dicts) built by
this factory itself, so ``strict=True`` here is behaviourally identical to
the previous default ``OpaquePolicy.RAISE`` - both refuse a non-JSON value
in ``options``/``components`` outright rather than digesting a different
form of it. What does change is the 12-hex-char slice's content: it is now
taken from ``content_hash``'s digest (after stripping its ``sha256:``
prefix) rather than ``CanonicalJson``'s bare digest, so every generated
knot id changes value across this upgrade - see the CHANGELOG entry.
Acceptable at this package's current 0.x version: a generated id is a
derived cache/lineage key, not data an operator persists across an upgrade
boundary the way an idempotency key is.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from pirn.core.hashing import content_hash


class AgentKnotIdFactory:
    """Derives stable, valid knot ids from an agent's structural signature."""

    @classmethod
    def _name_pattern(cls) -> re.Pattern[str]:
        """Return the regex an explicit ``name`` must satisfy."""
        return re.compile(r"^[a-zA-Z0-9_\-.]{1,200}$")

    @classmethod
    def derive(
        cls,
        *,
        pattern: str,
        llm: str | None = None,
        memory: str | None = None,
        tools: Sequence[str] = (),
        components: Mapping[str, str] | None = None,
        options: Mapping[str, Any] | None = None,
        name: str | None = None,
    ) -> str:
        """Return a deterministic, ``KnotConfig``-valid id for an agent graph.

        When ``name`` is supplied it becomes the id verbatim (prefixed with
        ``agent.``); otherwise a 12-hex-char digest of the canonical structural
        signature is appended so distinct configurations get distinct ids while
        identical ones collide.

        Args:
            pattern: The agentic pattern name.
            llm: Reference of the LLM provider, or ``None``.
            memory: Reference of the memory store, or ``None``.
            tools: References of the tools wired into the agent.
            components: References of the pattern's other components, keyed by
                constructor parameter name (embedder, store, specialists, …).
            options: Pattern options influencing the structure.
            name: Optional explicit name; when given, no digest is appended.

        Returns:
            A stable id string of the form ``agent.<name>`` or
            ``agent.<pattern>.<digest>``.

        Raises:
            ValueError: If ``pattern`` is empty, or ``name`` is given but does
                not match the allowed id character set.
        """
        if not pattern:
            raise ValueError("AgentKnotIdFactory.derive: pattern must be non-empty")
        if name is not None:
            if not cls._name_pattern().match(name):
                raise ValueError(
                    f"AgentKnotIdFactory.derive: name {name!r} must match "
                    "[a-zA-Z0-9_-.] and be 1-200 chars"
                )
            return f"agent.{name}"
        signature: dict[str, Any] = {
            "pattern": pattern,
            "llm": llm,
            "memory": memory,
            "tools": list(tools),
            "options": dict(options or {}),
        }
        # Only present when non-empty: an always-present key would change the
        # canonical form, and so every id previously derived for the three
        # llm/memory/tools patterns — breaking lineage continuity and cache
        # alignment for graphs that have not changed at all.
        if components:
            signature["components"] = dict(components)
        digest = content_hash(signature, strict=True).removeprefix("sha256:")[:12]
        safe_pattern = re.sub(r"[^a-zA-Z0-9_\-.]", "_", pattern)
        return f"agent.{safe_pattern}.{digest}"

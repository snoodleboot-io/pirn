"""``ContentHasher`` — content-addressed hashing of values.

Lineage records reference values by hash, not by content.  Two runs that
produce the same value should produce the same hash, regardless of which
process / machine / Python session computed it.  We therefore use a
*canonical* serialisation: the same Python value always serialises to the
same bytes.

For Pydantic models we use the model's own JSON serialisation (deterministic
field order).  For everything else we recurse into containers and fall back
to ``repr`` for opaque types — repr is not perfectly stable across Python
versions, but it is stable within a deployment, which is the lineage scope
that matters in practice.

The hash is sha256 over the canonical bytes, encoded as hex.  Hex (not
base64) because hashes appear in logs and JSON often, where hex is the
universal-readable form.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Mapping, Sequence, Set
from typing import Any, ClassVar

from pydantic import BaseModel, TypeAdapter

from pirn.core.unhashable_error import UnhashableError
from pirn.exceptions.unhashable_value_error import UnhashableValueError

_logger = logging.getLogger(__name__)


class ContentHasher:
    """Stateless utility computing stable content hashes for lineage joins.

    Exposed as static methods so call sites do not need to instantiate the
    hasher — mirrors :class:`pirn.engine.shed.cycle_detector.CycleDetector`.
    """

    #: Cache to avoid rebuilding ``TypeAdapter`` per ``_canonicalise`` call.
    #: Constructing a TypeAdapter walks the type and builds a schema/validator
    #: pair (~10-100 µs); at millions of canonicalisations per tapestry the
    #: cost compounds. Keyed by the runtime type so different concrete types
    #: remain isolated.
    _type_adapter_cache: ClassVar[dict[type, TypeAdapter]] = {}

    @staticmethod
    def hash(value: Any, *, strict: bool = False) -> str:
        """Return a stable hex sha256 of ``value`` suitable for lineage joins.

        Algorithm:
            1. Recursively canonicalise ``value`` via :meth:`_canonicalise`
               into a JSON-serialisable form (sorted-key mappings, tagged
               containers, hook/schema fallbacks for opaque leaves).
            2. If canonicalisation hits a leaf with no canonical form at all
               — no ``__pirn_canonical__``, no pydantic core schema, not a
               recognised container — :meth:`_canonicalise` raises
               ``UnhashableError`` naming that leaf's type. ``strict=True``
               re-raises it as :class:`~pirn.exceptions.unhashable_value_error.UnhashableValueError`;
               ``strict=False`` (the default) swallows it and returns a
               ``sha256:unhashable:<top-level type>`` sentinel instead, since
               most callers only need *a* stable-looking key and would
               rather get one than crash.
            3. Otherwise, JSON-encode the canonical form with tight
               separators and no key sorting (canonicalisation already
               sorted mapping keys) and take its UTF-8 SHA-256 hex digest,
               prefixed ``sha256:``.

        Stability rules
        ---------------
        * Pydantic models: hash of the model's JSON serialisation with sorted
          keys.  Two structurally identical models hash the same.
        * Mappings (dict): keys are sorted (lexicographic on str(key)) before
          serialisation.
        * Sequences (list, tuple): element order is preserved (it is part of
          the value).
        * Sets / frozensets: elements are hashed individually then sorted; the
          set hash is order-independent.
        * Primitives (str, int, float, bool, None): JSON-encoded.
        * Bytes: hex-encoded then JSON-wrapped (so they round-trip).
        * Anything else: ``repr(value)`` — best-effort.  Returns ``UNHASHABLE``
          prefix to signal the caller can't reliably compare across processes,
          unless ``strict=True``.

        Args:
            value: The value to hash.
            strict: When ``True``, raise
                :class:`~pirn.exceptions.unhashable_value_error.UnhashableValueError`
                (naming the innermost offending type) instead of returning
                the ``sha256:unhashable:<type>`` sentinel for a value with no
                canonical form. Defaults to ``False`` — unchanged legacy
                behaviour.

        Raises:
            UnhashableValueError: If ``strict`` is ``True`` and ``value``
                contains a leaf with no canonical form.
        """
        try:
            canonical = ContentHasher._canonicalise(value, strict=strict)
        except UnhashableError as exc:
            if strict:
                raise UnhashableValueError(type_name=exc.type_name) from exc
            return f"sha256:{UnhashableError.sentinel}:{type(value).__name__}"
        payload = json.dumps(canonical, separators=(",", ":"), sort_keys=False).encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        return f"sha256:{digest}"

    @staticmethod
    def _opaque_fallback(opaque_value: Any) -> Any:
        """Fallback used when a Pydantic model dumps an opaque payload field.

        Prefers the established ``_pirn_audit_dict()`` contract; falls back
        to ``repr`` for values that don't declare it — the same last-resort
        ``ContentHasher._canonicalise`` itself uses for truly opaque values.
        """
        if hasattr(opaque_value, "_pirn_audit_dict"):
            return opaque_value._pirn_audit_dict()
        return repr(opaque_value)

    @staticmethod
    def _canonicalise(value: Any, *, strict: bool = False) -> Any:
        """Recursively convert ``value`` into a JSON-serialisable canonical form.

        We use prefixed type tags ("__bytes__", "__set__", etc.) to ensure
        distinguishable hashes for values that would otherwise collide once
        serialised.  Without the tags, ``{"x": 1}`` and ``["x", 1]`` could in
        principle hash the same after JSON serialisation; with the tags they
        cannot.

        Two extension hooks are honoured ahead of the built-in branches:

        * ``__pirn_canonical__()`` — sanctioned, type-controlled hook. A type
          that wants explicit control over its content-hash form returns a
          primitive (dict / list / str / int / etc.) and ``_canonicalise``
          recurses into the result. This is the preferred form because it is
          cheap (no pydantic round-trip) and makes the canonical shape
          visible at the call site of the hook.
        * Pydantic-aware fallback for types declaring
          ``__get_pydantic_core_schema__`` but **not** subclassing
          ``BaseModel`` (e.g. frozen dataclasses backed by
          :class:`PirnOpaqueValue`). ``TypeAdapter.dump_python`` honours the
          type's custom serialiser, producing a JSON-friendly dict that we
          then canonicalise normally. Without this branch the canonicaliser
          walks dataclass ``type`` fields and hits ``UnhashableError`` for
          anything containing a ``Mapping[str, type]`` (DataSchema columns).

        Args:
            value: The value to canonicalise.
            strict: Forwarded to the one recursive call that does not go
                through ``_canonicalise`` itself — the per-element sub-hash
                inside the set/frozenset branch, which calls
                :meth:`hash` directly. Every other branch recurses via
                ``_canonicalise``, and ``UnhashableError`` from a nested
                call propagates unmodified regardless of ``strict`` — this
                method never catches it, only :meth:`hash` does.
        """
        # Primitive isinstance check FIRST — common case; avoids the
        # ``hasattr`` exception path for every plain int/str/bool/None.
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        if isinstance(value, bytes):
            return {"__bytes__": value.hex()}
        # Sanctioned hook — types control their canonical form explicitly
        # when this is defined.
        if hasattr(value, "__pirn_canonical__"):
            return ContentHasher._canonicalise(value.__pirn_canonical__(), strict=strict)
        if isinstance(value, BaseModel):
            # Model JSON, then re-canonicalise the resulting dict so nested
            # non-Pydantic values are handled consistently.
            #
            # Pass a fallback to handle opaque payload types (PirnOpaqueValue
            # dataclasses with np.ndarray fields) that pydantic's runtime
            # dict[str, Any] serialiser cannot reach via __get_pydantic_core_schema__
            # alone.  _pirn_audit_dict() is the established contract; repr is the
            # last-resort fallback that _canonicalise itself uses for truly opaque
            # values.
            return {
                "__model__": value.__class__.__name__,
                "data": ContentHasher._canonicalise(
                    value.model_dump(mode="json", fallback=ContentHasher._opaque_fallback),
                    strict=strict,
                ),
            }
        # Pydantic-aware fallback for non-``BaseModel`` types declaring a
        # custom core schema. Excludes containers so the dedicated branches
        # below remain authoritative. ``TypeAdapter`` instances are cached
        # per concrete type to amortise schema-construction cost.
        if not isinstance(value, (list, tuple, dict, set, frozenset)) and hasattr(
            type(value), "__get_pydantic_core_schema__"
        ):
            value_type = type(value)
            try:
                adapter = ContentHasher._type_adapter_cache.get(value_type)
                if adapter is None:
                    adapter = TypeAdapter(value_type)
                    ContentHasher._type_adapter_cache[value_type] = adapter
                return ContentHasher._canonicalise(
                    adapter.dump_python(value, mode="json"), strict=strict
                )
            except Exception:
                # Fall through to the container/Mapping/Sequence branches
                # below; if those also fail we end up at ``UnhashableError``.
                _logger.warning(
                    "ContentHasher: TypeAdapter.dump_python failed for %s; "
                    "falling back to container/repr canonicalisation",
                    value_type,
                    exc_info=True,
                )
        if isinstance(value, Mapping):
            # Sort by str(key) for determinism.  Keys must serialise to strings
            # in JSON anyway.
            return {
                "__map__": [
                    [
                        ContentHasher._canonicalise(k, strict=strict),
                        ContentHasher._canonicalise(value[k], strict=strict),
                    ]
                    for k in sorted(value.keys(), key=str)
                ]
            }
        if isinstance(value, (set, frozenset, Set)):
            # Hash each element separately, then sort element-hashes for an
            # order-independent canonical form. Goes through ``hash()``, not
            # ``_canonicalise()``, so ``strict`` must be passed explicitly —
            # this is the one place a nested failure would otherwise be
            # silently absorbed into a per-element sentinel rather than
            # reaching the outer ``hash()`` call's ``except``.
            element_hashes = sorted(ContentHasher.hash(e, strict=strict) for e in value)
            return {"__set__": element_hashes}
        if isinstance(value, (list, tuple, Sequence)) and not isinstance(value, (str, bytes)):
            return {"__seq__": [ContentHasher._canonicalise(e, strict=strict) for e in value]}
        # Opaque type — bail.  Caller produces the UNHASHABLE marker (or, in
        # strict mode, UnhashableValueError naming this exact type).
        raise UnhashableError(type_name=type(value).__name__)

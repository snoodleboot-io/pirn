"""Content-addressed hashing of values.

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
from collections.abc import Mapping, Sequence, Set
from typing import Any

from pydantic import BaseModel, RootModel, TypeAdapter

# Module-level cache to avoid rebuilding ``TypeAdapter`` per
# ``_canonicalise`` call. Constructing a TypeAdapter walks the type and
# builds a schema/validator pair (~10-100 µs); at millions of
# canonicalisations per tapestry the cost compounds. Keyed by the runtime
# type so different concrete types remain isolated.
_type_adapter_cache: dict[type, TypeAdapter] = {}


class _UnhashableError(Exception):
    """Internal sentinel used by ``_canonicalise`` to bail on opaque values."""

    sentinel = "unhashable"


def content_hash(value: Any) -> str:
    """Return a stable hex sha256 of ``value`` suitable for lineage joins.

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
      prefix to signal the caller can't reliably compare across processes.
    """
    try:
        canonical = _canonicalise(value)
    except _UnhashableError:
        return f"sha256:{_UnhashableError.sentinel}:{type(value).__name__}"
    payload = json.dumps(canonical, separators=(",", ":"), sort_keys=False).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return f"sha256:{digest}"


def _canonicalise(value: Any) -> Any:
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
      visible at the call site of the hook. It is honoured for values
      nested inside a pydantic model too (see
      :func:`_restore_canonical_hooks`), not only at the top level.
    * Pydantic-aware fallback for types declaring
      ``__get_pydantic_core_schema__`` but **not** subclassing
      ``BaseModel`` (e.g. frozen dataclasses backed by
      :class:`PirnOpaqueValue`). ``TypeAdapter.dump_python`` honours the
      type's custom serialiser, producing a JSON-friendly dict that we
      then canonicalise normally. Without this branch the canonicaliser
      walks dataclass ``type`` fields and hits ``_UnhashableError`` for
      anything containing a ``Mapping[str, type]`` (DataSchema columns).
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
        return _canonicalise(value.__pirn_canonical__())
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
        def _opaque_fallback(opaque_value: Any) -> Any:
            if hasattr(opaque_value, "_pirn_audit_dict"):
                return opaque_value._pirn_audit_dict()
            return repr(opaque_value)

        dumped = value.model_dump(mode="json", fallback=_opaque_fallback)
        return {
            "__model__": value.__class__.__name__,
            "data": _canonicalise(_restore_canonical_hooks(value, dumped)),
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
            adapter = _type_adapter_cache.get(value_type)
            if adapter is None:
                adapter = TypeAdapter(value_type)
                _type_adapter_cache[value_type] = adapter
            return _canonicalise(adapter.dump_python(value, mode="json"))
        except Exception:
            # Fall through to the container/Mapping/Sequence branches
            # below; if those also fail we end up at ``_UnhashableError``.
            pass
    if isinstance(value, Mapping):
        # Sort by str(key) for determinism.  Keys must serialise to strings
        # in JSON anyway.
        return {
            "__map__": [
                [_canonicalise(k), _canonicalise(value[k])] for k in sorted(value.keys(), key=str)
            ]
        }
    if isinstance(value, (set, frozenset, Set)):
        # Hash each element separately, then sort element-hashes for an
        # order-independent canonical form.
        element_hashes = sorted(content_hash(e) for e in value)
        return {"__set__": element_hashes}
    if isinstance(value, (list, tuple, Sequence)) and not isinstance(value, (str, bytes)):
        return {"__seq__": [_canonicalise(e) for e in value]}
    # Opaque type — bail.  Caller produces the UNHASHABLE marker.
    raise _UnhashableError


def _restore_canonical_hooks(model: BaseModel, dumped: Any) -> Any:
    """Route every value nested in ``model`` that has a canonical hook back to it.

    ``model_dump`` serialises a nested opaque value through its pydantic
    serialiser, which is its audit form. For a connector the audit form is a
    per-class constant, so ``Settings(connector=a)`` and
    ``Settings(connector=b)`` would dump, and hash, the same (PIR-848).

    Wherever the dump holds such a value, in a field typed as the class, as
    ``Any``, inside a list, tuple, set or mapping, or in a nested model, this
    puts the live object back so the outer ``_canonicalise`` reaches its
    ``__pirn_canonical__``. Everything around it keeps its dumped JSON form. A
    model holding no hook object is returned untouched and hashes exactly as
    before. Fields the dump excludes stay excluded.

    Args:
        model: The model that was dumped.
        dumped: ``model.model_dump(mode="json")`` output.

    Returns:
        ``dumped``, or a shallow-rebuilt copy with hook objects restored.
    """
    if isinstance(model, RootModel):
        # A RootModel dumps to its bare root value, which may itself be a dict.
        return _merge_canonical_hooks(model.root, dumped)
    if not isinstance(dumped, dict):
        return dumped
    restored: dict[str, Any] | None = None
    # Field values live in the instance ``__dict__``; extras in
    # ``__pydantic_extra__``. Aliases are looked up only for a hit.
    for values in (model.__dict__, model.__pydantic_extra__ or {}):
        for name, raw in values.items():
            if not _holds_canonical_hook(raw):
                continue
            field = type(model).model_fields.get(name)
            keys = (name,) if field is None else (name, field.serialization_alias, field.alias)
            for key in keys:
                if key is not None and key in dumped:
                    restored = dict(dumped) if restored is None else restored
                    restored[key] = _merge_canonical_hooks(raw, dumped[key])
                    break
    return dumped if restored is None else restored


def _merge_canonical_hooks(raw: Any, dumped: Any) -> Any:
    """Merge one raw value with its dumped form, keeping hook objects live.

    Lists, tuples and string-keyed mappings are walked in step with their dump,
    so only the hook-holding elements change. A nested model is handed back
    whole; the ``BaseModel`` branch of ``_canonicalise`` dumps and restores it
    itself. A set, or a shape the dump no longer mirrors (a custom field
    serialiser, say), falls back to the raw value, which ``_canonicalise``
    walks directly.
    """
    if not _holds_canonical_hook(raw):
        return dumped
    if hasattr(raw, "__pirn_canonical__") or isinstance(raw, BaseModel):
        return raw
    if isinstance(raw, (list, tuple)) and isinstance(dumped, list) and len(raw) == len(dumped):
        return [_merge_canonical_hooks(r, d) for r, d in zip(raw, dumped, strict=True)]
    if (
        isinstance(raw, Mapping)
        and isinstance(dumped, dict)
        and all(isinstance(k, str) and k in dumped for k in raw)
    ):
        return {k: _merge_canonical_hooks(raw[k], d) if k in raw else d for k, d in dumped.items()}
    return raw


def _holds_canonical_hook(value: Any) -> bool:
    """Whether ``value`` is, or contains, an object defining ``__pirn_canonical__``.

    Walks the same shapes ``_canonicalise`` walks, plus nested model fields.
    This runs for every model hashed, so primitives and exact builtin
    containers are tested by type before the comparatively slow ``hasattr``.
    """
    if value is None or isinstance(value, (bool, int, float, str, bytes)):
        return False
    value_type = type(value)
    if value_type is list or value_type is tuple or value_type is set or value_type is frozenset:
        for item in value:
            if item is None or isinstance(item, (bool, int, float, str, bytes)):
                continue
            if _holds_canonical_hook(item):
                return True
        return False
    if value_type is dict:
        for key, item in value.items():
            if item is not None and not isinstance(item, (bool, int, float, str, bytes)):
                if _holds_canonical_hook(item):
                    return True
            if not isinstance(key, str) and _holds_canonical_hook(key):
                return True
        return False
    if hasattr(value, "__pirn_canonical__"):
        return True
    if isinstance(value, BaseModel):
        return _holds_canonical_hook(dict(value.__dict__)) or _holds_canonical_hook(
            dict(value.__pydantic_extra__ or {})
        )
    if isinstance(value, Mapping):
        return _holds_canonical_hook(dict(value))
    if isinstance(value, (list, tuple, set, frozenset)):
        return _holds_canonical_hook(list(value))
    return False

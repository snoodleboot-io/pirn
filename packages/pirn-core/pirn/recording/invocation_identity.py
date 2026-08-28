"""What must agree for two knot invocations to be the same computation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pirn.core.hashing import content_hash

if TYPE_CHECKING:
    from pirn.core.knot import Knot


class InvocationIdentity:
    """Hashes the part of a knot's inputs that lineage does not already cover.

    ``KnotLineage`` records ``knot_config_hash`` and ``parent_input_hashes``,
    which between them describe a knot's framework configuration and every
    value that reached it from a parent.  They do **not** describe the literal
    arguments passed to the knot's constructor — ``Scale(x=parent, factor=3)``
    keeps ``factor`` in ``Knot.config_values``, and it reaches ``process()``
    as an input without ever being hashed.

    Two such knots therefore record identical ``knot_config_hash``, identical
    ``parent_input_hashes`` and identical ``source_hash`` while computing
    different answers.  That is harmless for a re-executing helper like
    ``pirn.replay.replay_run`` — the knot runs, so the literal is honoured —
    but it is fatal for a replay that *substitutes* the recorded output: the
    stale value would be served with no signal that anything had changed.

    This class closes that hole by hashing ``config_values`` into the lineage
    row's ``config_values_hash`` field, so replay can compare it.  It is
    deliberately not folded into ``knot_config_hash``: that hash is a published
    cross-run join key and changing what it covers would invalidate every
    stored history (PIR-836).

    Not every literal is comparable, and the failure is not symmetric:

    * plain values (``int``, ``str``, ``dict``, ...) get a true content hash;
    * a :class:`~pirn.core.pirn_opaque_value.PirnOpaqueValue` — an LLM
      provider, a tool, a connection pool — is *identity-keyed*, so the same
      logical object hashes differently in another process.  That produces a
      false *mismatch*, which is safe: replay refuses and the knot executes;
    * a fully opaque object with no pydantic schema canonicalises to
      ``sha256:unhashable:<Type>``, which is **equal for two different
      instances**.  That produces a false *match*, which is not safe: a
      recorded output would be served for a knot configured with a different
      object.

    :meth:`is_comparable` exists so callers can refuse the third case rather
    than trusting an equality that does not mean what it looks like.
    """

    #: Marker ``content_hash`` emits when a value has no canonical form.  Every
    #: instance of such a type shares it, so it can never establish identity.
    UNCOMPARABLE_MARKER = ":unhashable:"

    @staticmethod
    def config_values_hash(knot: Knot) -> str | None:
        """Return a content hash of ``knot``'s literal constructor arguments.

        Returns ``None`` when the knot has none, so the common case adds
        nothing to the lineage row and ``None == None`` is a valid match.

        Args:
            knot: The knot whose literal (non-parent) inputs to hash.

        Returns:
            A ``sha256:``-prefixed hex digest, or ``None`` if there are no
            literal inputs.  The digest may be an ``unhashable`` marker — see
            :meth:`is_comparable` before treating equality as identity.
        """
        values = dict(knot.config_values)
        if not values:
            return None
        return content_hash(values)

    @classmethod
    def is_comparable(cls, config_values_hash: str | None) -> bool:
        """Whether equality of ``config_values_hash`` establishes identity.

        ``None`` (no literals) is comparable: two knots without literals
        genuinely agree.  A digest is comparable.  An ``unhashable`` marker is
        not — it is shared by every instance of the offending type, so two
        knots holding *different* objects compare equal.

        Args:
            config_values_hash: A value produced by :meth:`config_values_hash`,
                or read back from a stored ``KnotLineage`` row.

        Returns:
            ``True`` when equality may be trusted, ``False`` when it may not.
        """
        if config_values_hash is None:
            return True
        return cls.UNCOMPARABLE_MARKER not in config_values_hash

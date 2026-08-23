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
    row's ``extra``, so replay can compare it.  It is deliberately not folded
    into ``knot_config_hash``: that hash is a published cross-run join key and
    changing what it covers would invalidate every stored history.
    """

    @staticmethod
    def config_values_hash(knot: Knot) -> str | None:
        """Return a content hash of ``knot``'s literal constructor arguments.

        Returns ``None`` when the knot has none, so the common case adds
        nothing to the lineage row and ``None == None`` is a valid match.

        Args:
            knot: The knot whose literal (non-parent) inputs to hash.

        Returns:
            A ``sha256:``-prefixed hex digest, or ``None`` if there are no
            literal inputs.
        """
        values = dict(knot.config_values)
        if not values:
            return None
        return content_hash(values)

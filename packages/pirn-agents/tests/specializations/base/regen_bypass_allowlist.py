"""``BypassAllowlistRegenerator`` — recompute the ``test_no_engine_bypass.py`` allowlists.

Run this after merging other lanes' remediation work, since the inventory
this test freezes is being reduced concurrently by other lanes (PIR-856) and
by future work generally:

.. code-block:: shell

    python -m tests.specializations.base.regen_bypass_allowlist

from the package root (``packages/pirn-agents``). It prints all seven
frozenset literals, computed against the *current* working tree, ready to
paste directly over the ones near the top of ``test_no_engine_bypass.py``.
Fixing a pipeline and forgetting to update its allowlist entry is exactly
what the exact-equality assertions in that file are designed to catch — this
script exists so "update the list" is a paste, not a manual diff.
"""

from __future__ import annotations

from collections.abc import Callable

from tests.specializations.base.bypass_inventory import BypassInventory


class BypassAllowlistRegenerator:
    """Prints the seven frozenset literals ``test_no_engine_bypass.py`` freezes."""

    @staticmethod
    def _checks() -> tuple[tuple[str, Callable[[object], bool]], ...]:
        return (
            ("AWAITS_CHILD_PROCESS", BypassInventory.awaits_child_process),
            ("RETURNS_INLINE_SOURCE", BypassInventory.returns_inline_source),
            ("UNRUN_TAPESTRY", BypassInventory.opens_unrun_tapestry),
            ("AWAITS_INVOKE", BypassInventory.awaits_invoke),
            ("USES_ASYNCIO_GATHER", BypassInventory.uses_asyncio_gather),
            ("LOOP_AWAITS_LLM_OR_TOOL_CALL", BypassInventory.loop_awaits_llm_or_tool_call),
            ("HAND_ROLLED_WHILE_TRUE_RETRY", BypassInventory.hand_rolled_while_true_retry),
        )

    @classmethod
    def render(cls) -> str:
        """Return the seven allowlists as pasteable Python source."""
        found = BypassInventory.discover_process_methods()
        blocks: list[str] = []
        for constant_name, checker in cls._checks():
            hits = sorted(label for label, process in found.items() if checker(process))
            lines = [f"{constant_name} = frozenset("]
            if hits:
                lines.append("    {")
                lines.extend(f"        {hit!r}," for hit in hits)
                lines.append("    }")
            else:
                lines.append("    set()")
            lines.append(")")
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)

    @classmethod
    def main(cls) -> None:
        """Print the regenerated allowlists to stdout."""
        print(cls.render())


if __name__ == "__main__":
    BypassAllowlistRegenerator.main()

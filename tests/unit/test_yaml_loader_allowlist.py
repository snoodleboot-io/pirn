"""Tests for the import allowlist feature in the YAML pipeline loader (H-2)."""

from __future__ import annotations
import unittest


from pirn.yaml_loader.loader import load_pipeline

# Minimal YAML that exercises a knot with a callable ref.
_KNOT_YAML_TEMPLATE = """\
allow_callable_refs: {allow}
{prefixes_line}
nodes:
  - type: source
    id: src
    callable: {ref}
"""


def _yaml(ref: str, allow: bool = True, prefixes: list[str] | None = None) -> str:
    if prefixes is not None:
        prefixes_line = f"allowed_module_prefixes: {prefixes!r}"
    else:
        prefixes_line = ""
    return _KNOT_YAML_TEMPLATE.format(
        allow="true" if allow else "false",
        prefixes_line=prefixes_line,
        ref=ref,
    )


class TestAllowlistPassthrough(unittest.TestCase):
    """Caller-supplied allowed_module_prefixes via load_pipeline kwarg."""

    def test_allowed_prefix_passes(self) -> None:
        """A ref in the allowed prefix is resolved without error."""
        # pirn.core.knot.Knot is a class; the source wraps any callable,
        # so even a class ref is accepted here at resolution time.
        load_pipeline(
            _yaml("pirn.core.knot.Knot", allow=True),
            allowed_module_prefixes=["pirn"],
        )

    def test_disallowed_prefix_raises(self) -> None:
        """A ref outside the allowed prefix raises ValueError."""
        with self.assertRaisesRegex(ValueError, "allowed_module_prefixes"):
            load_pipeline(
                _yaml("os.system", allow=True),
                allowed_module_prefixes=["myapp"],
            )

    def test_no_allowlist_any_import_allowed(self) -> None:
        """Without an allowlist, any dotted ref is imported (with warning)."""
        # os.getcwd is a safe callable that exists in stdlib.
        load_pipeline(
            _yaml("os.getcwd", allow=True),
            allowed_module_prefixes=None,
        )

    def test_allow_callable_refs_false_raises_regardless(self) -> None:
        """When allow_callable_refs=False, unknown refs raise regardless of allowlist."""
        with self.assertRaisesRegex(ValueError, "allow_callable_refs"):
            load_pipeline(
                _yaml("pirn.core.knot.Knot", allow=False),
                allowed_module_prefixes=["pirn"],
            )


class TestAllowlistInYAML(unittest.TestCase):
    """allowed_module_prefixes specified inside the YAML spec."""

    def test_yaml_allowlist_blocks_disallowed(self) -> None:
        """allowed_module_prefixes in YAML blocks imports outside the list."""
        with self.assertRaisesRegex(ValueError, "allowed_module_prefixes"):
            load_pipeline(_yaml("os.system", allow=True, prefixes=["myapp"]))

    def test_yaml_allowlist_permits_allowed(self) -> None:
        """allowed_module_prefixes in YAML permits imports inside the list."""
        load_pipeline(_yaml("pirn.core.knot.Knot", allow=True, prefixes=["pirn"]))

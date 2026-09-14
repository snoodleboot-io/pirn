"""CLI entry point for ``tapestry-check``."""

from __future__ import annotations

import argparse
import sys

from pirn.check.factory_spec_loader import FactorySpecLoader
from pirn.check.tapestry_validator import TapestryValidator


class TapestryCheckCli:
    """Implementation of the ``tapestry-check`` console script."""

    @staticmethod
    def main(argv: list[str] | None = None) -> int:
        parser = argparse.ArgumentParser(
            prog="tapestry-check",
            description="Statically validate a pirn tapestry for structural issues.",
        )
        parser.add_argument("spec", help="MODULE:FUNCTION — e.g. myapp.pipeline:build_tapestry")
        parser.add_argument("--strict", action="store_true", help="Treat warnings as errors.")
        args = parser.parse_args(argv)

        factory = FactorySpecLoader.load_factory(args.spec)

        try:
            tapestry = factory()
        except Exception as exc:
            print(f"error: factory raised {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2

        result = TapestryValidator.validate(tapestry)

        for issue in result.issues:
            print(issue)

        if not result.issues:
            knot_count = len(tapestry._store.all())
            print(f"ok — {knot_count} knots, no issues found")

        if args.strict and result.warnings:
            return 1

        return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(TapestryCheckCli.main())

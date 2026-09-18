"""Run the content moderation tapestry defined in tapestry.yaml.

Demonstrates loading a tapestry from YAML and running it with several
test inputs that exercise the allow / warn / block paths.

Run with:
    uv run python -m examples.content_moderation
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn.yaml_loader.pipeline_loader import PipelineLoader


class ContentModeration:
    """Loads ``tapestry.yaml`` and runs it over a fixed set of sample texts."""

    samples: ClassVar[tuple[tuple[str, str], ...]] = (
        ("Clean text", "The quick brown fox jumps over the lazy dog."),
        ("Profanity", "This is badword content that is offensive."),
        ("PII — email", "Please contact alice@example.com for support."),
        ("PII — phone", "Call us on 555-867-5309 any time."),
        ("High caps/toxic", "BADWORD SPAM THIS IS OFFENSIVE SPAM BADWORD!!!"),
        ("Unknown lang", "Hélas, il était une fois dans un pays lointain…"),
    )

    @classmethod
    async def main(cls) -> None:
        """Run every sample through the YAML-defined tapestry and print its lineage."""
        yaml_path = Path(__file__).parent / "tapestry.yaml"
        history = SQLiteHistory(
            path=str(Path(__file__).resolve().parent.parent / "pirn.db")
        )
        base_tapestry = Tapestry(history=history)
        tapestry = PipelineLoader.load_yaml(
            yaml_path.read_text(), tapestry=base_tapestry
        )

        for label, text in cls.samples:
            print(f"\n── {label} ──")
            result = await tapestry.run(RunRequest(parameters={"raw_text": text}))
            for rec in result.lineage:
                icon = (
                    "✓"
                    if rec.outcome == "ok"
                    else ("⊘" if rec.outcome == "skipped" else "✗")
                )
                print(f"  {icon} {rec.knot_id:<18} {rec.outcome}")

        history.close()

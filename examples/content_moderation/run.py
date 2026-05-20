"""Run the content moderation tapestry defined in tapestry.yaml.

Demonstrates loading a tapestry from YAML and running it with several
test inputs that exercise the allow / warn / block paths.

Run with:
    uv run python examples/content_moderation/run.py
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from pirn.backends.sqlite.sqlite_history import SQLiteHistory
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn.yaml_loader.loader import load_pipeline

YAML_PATH = Path(__file__).parent / "tapestry.yaml"
DB_PATH = Path(__file__).parent.parent / "pirn.db"

SAMPLES = [
    ("Clean text", "The quick brown fox jumps over the lazy dog."),
    ("Profanity", "This is badword content that is offensive."),
    ("PII — email", "Please contact alice@example.com for support."),
    ("PII — phone", "Call us on 555-867-5309 any time."),
    ("High caps/toxic", "BADWORD SPAM THIS IS OFFENSIVE SPAM BADWORD!!!"),
    ("Unknown lang", "Hélas, il était une fois dans un pays lointain…"),
]


async def main() -> None:
    history = SQLiteHistory(path=str(DB_PATH))
    base_tapestry = Tapestry(history=history)
    tapestry = load_pipeline(YAML_PATH.read_text(), tapestry=base_tapestry)

    for label, text in SAMPLES:
        print(f"\n── {label} ──")
        result = await tapestry.run(RunRequest(parameters={"raw_text": text}))
        for rec in result.lineage:
            icon = "✓" if rec.outcome == "ok" else ("⊘" if rec.outcome == "skipped" else "✗")
            print(f"  {icon} {rec.knot_id:<18} {rec.outcome}")

    history.close()


if __name__ == "__main__":
    asyncio.run(main())

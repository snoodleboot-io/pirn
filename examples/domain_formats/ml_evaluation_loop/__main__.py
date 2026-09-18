"""Entry point: ``python -m examples.domain_formats.ml_evaluation_loop``."""

import asyncio

from examples.domain_formats.ml_evaluation_loop.ml_evaluation_loop import MlEvaluationLoop

if __name__ == "__main__":
    asyncio.run(MlEvaluationLoop.main())

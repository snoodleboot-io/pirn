"""Entry point: ``python -m examples.financial.fraud_detection``."""

import asyncio

from examples.financial.fraud_detection.fraud_detection import FraudDetection

if __name__ == "__main__":
    asyncio.run(FraudDetection.main())

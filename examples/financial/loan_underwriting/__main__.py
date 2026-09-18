"""Entry point: ``python -m examples.financial.loan_underwriting``."""

import asyncio

from examples.financial.loan_underwriting.loan_underwriting import LoanUnderwriting

if __name__ == "__main__":
    asyncio.run(LoanUnderwriting.main())

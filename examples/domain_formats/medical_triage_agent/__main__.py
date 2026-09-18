"""Entry point: ``python -m examples.domain_formats.medical_triage_agent``."""

import asyncio

from examples.domain_formats.medical_triage_agent.medical_triage_agent import MedicalTriageAgent

if __name__ == "__main__":
    asyncio.run(MedicalTriageAgent.main())

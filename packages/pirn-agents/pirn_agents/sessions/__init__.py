"""Durable sessions & HITL resume (F14): a serializable run-state / checkpoint
model, a provider-neutral ``SessionStore`` with in-memory and persisted adapters,
``checkpoint()`` / ``resume()`` with idempotent re-entry, HITL suspend→persist→
resume, and durable multi-turn thread persistence."""

__all__: list[str] = []

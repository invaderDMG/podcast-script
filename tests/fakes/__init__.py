"""Reusable test doubles (POD-030).

Lives outside :mod:`tests.contract` and :mod:`tests.unit` so Tier 1
tests can adopt the same fakes once POD-029's reorganisation lands —
keeping a single canonical FakeBackend prevents fake-vs-fake drift.
"""

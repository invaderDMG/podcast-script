"""Reusable test doubles (POD-030).

Lives outside :mod:`tests.contract` and :mod:`tests.unit` so both
tiers share a single canonical ``FakeBackend`` (see
:mod:`tests.fakes.whisper`) — preventing the fake-vs-fake drift that
ADR-0017 calls out as the load-bearing failure mode of split-tier
test doubles. Tier 1 lives at :mod:`tests.unit` (POD-029); Tier 2
contract tests live at :mod:`tests.contract` and parametrise the same
``FakeBackend`` against each real backend.
"""

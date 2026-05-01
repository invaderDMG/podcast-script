"""Tier 2 contract tests (POD-030, ADR-0017).

A shared parametrized suite asserting :class:`WhisperBackend` Protocol
invariants identically against ``FakeBackend`` and each real backend
(``FasterWhisperBackend`` / ``MlxWhisperBackend``). Real-backend
parametrisations skip cleanly when their library is not importable per
ADR-0011 — so a Linux developer's ``pytest -m contract`` works without
``mlx_whisper`` installed; CI runs the matrix with both libs present.
"""

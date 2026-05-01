"""Tier 1 unit tests (POD-029, ADR-0017).

Pure logic + fakes; no real models, no ``ffmpeg`` subprocess, no heavy
deps. Suite target ≤ 1 s. Tests cover C-Decode, C-Render, C-Config,
errors, segment-merge (incl. property tests under POD-032), atomic
write, logging setup, progress, pipeline orchestration, CLI surface,
backend wrappers (lazy-import boundary asserted), and ``select_backend``.

Tests in this package consume the shared ``FakeBackend`` from
:mod:`tests.fakes.whisper` so Tier 1 and Tier 2 share one canonical
double — preventing fake-vs-fake drift that ADR-0017 calls out.
"""

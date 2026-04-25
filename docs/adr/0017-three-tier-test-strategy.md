# ADR-0017: Three-tier test strategy — unit / contract / integration

- **Status:** Accepted
- **Date:** 2026-04-25
- **Deciders:** Solo maintainer
- **Supersedes:** —

## Context
`SRS.md` §14.1 and `PROJECT_BRIEF.md` §8 sketch a two-tier setup: pytest unit tests with mocked backends, plus integration tests against `examples/sample.mp3` with `--model tiny` in CI on Ubuntu + macOS. NFR-8 requires `mypy --strict` clean and ≥ 80% line coverage overall, 100% on the segmentation-merge module.

The `WhisperBackend` Protocol (ADR-0003) is the load-bearing testability seam: unit tests inject fake backends to avoid pulling in `faster-whisper` / `mlx-whisper` / `inaSpeechSegmenter` / `ffmpeg`. This works as long as the **fake's behaviour matches the real implementations' behaviour** — which is exactly the kind of invariant that drifts silently as third-party libraries upgrade or as we add edge cases to the real adapters but forget to update the fake.

A two-tier strategy (unit + full integration) catches drift only via the slow integration job — and only for the cases the integration fixture exercises (one ~60 s Spanish clip, structural assertions on `tiny`-model output). Drift in subtler invariants (e.g. "transcribe of empty PCM yields an empty Iterable", "transcribe yields `TranscribedSegment`s in non-decreasing time order", "transcribe handles a slice shorter than the model's window") is invisible to both tiers.

## Decision
Adopt a **three-tier test strategy**:

### Tier 1 — Unit tests (`tests/unit/`)
Pure logic, no heavy deps, no real models, no ffmpeg subprocess. Targets:

- Config merging (TOML × CLI override precedence — AC-US-4.1, 4.2).
- Language validation + Levenshtein "did you mean?" suggestion (AC-US-1.5, AC-US-4.4).
- Render output for synthetic `Segment` + `TranscribedSegment` lists (AC-US-2.1..2.5, both `MM:SS` and `HH:MM:SS` branches).
- Atomic-write semantics — temp file unlinked on simulated mid-write failure (AC-US-6.3).
- Logfmt formatter shape — every `event=…` token in the catalogue produces a parseable line (NFR-10, ADR-0012).
- Exception-class `exit_code` table — parametrized assertion that NFR-9 mappings are stable (ADR-0006).

Speed target: full suite ≤ 1 s. Tests run without `faster-whisper`, `mlx-whisper`, `inaSpeechSegmenter`, or `ffmpeg` installed. The fake backend is a 30-line class implementing `WhisperBackend` that yields canned `TranscribedSegment`s.

### Tier 2 — Contract tests (`tests/contract/`)
A **shared parametrized test suite** that runs against both the fake and each real `WhisperBackend` implementation, asserting the Protocol's behavioural invariants:

- `transcribe(empty_pcm, lang)` yields an empty Iterable without error.
- `transcribe(silence_pcm, lang)` does not raise (it may yield empty or yield zero-text segments — both acceptable).
- Yielded `TranscribedSegment.start` values are non-decreasing within a single call.
- `transcribe` is callable repeatedly on the same backend instance after `load()` (no implicit single-use state).
- A `ModelError` is raised (not `RuntimeError` / `ValueError`) when the underlying library reports a model-load failure.

Implementation: a pytest fixture parametrized as `[FakeBackend, FasterWhisperBackend, MlxWhisperBackend]`; the same `test_*` functions run against all three. The real-backend parametrizations are **skipped** when the underlying library is not importable (so a Linux developer's `pytest` run still works without `mlx-whisper` installed; CI runners install both and run all parametrizations).

Contract tests use `--model tiny` to keep wall time tractable (~10 s per real backend per test). They do not need the `examples/sample.mp3` fixture; they generate synthetic PCM (silence, simple sine waves, a clip of speech audio under 5 seconds) inline.

This tier is what catches "the fake is no longer behaving like the real thing" — the failure mode that makes Tier 1's mocked unit tests give false confidence.

### Tier 3 — Integration tests (`tests/integration/`)
Full CLI end-to-end on `examples/sample.mp3` with `--model tiny`, real `ffmpeg`, real segmenter, real backend. One job per OS (Ubuntu uses `faster-whisper`; macOS uses `mlx-whisper` — `PROJECT_BRIEF.md` §9). Assertions are structural per `SRS.md` §14.1:

- Exit 0.
- Output file exists at the expected path.
- Markdown contains at least one `> [<ts> — music starts]` line and one matching `music ends`.
- All timestamps are `MM:SS` (since the fixture is < 1 h — AC-US-2.4).
- No `noise`/`silence` annotation lines (AC-US-2.5).
- Logfmt summary line on stderr matches the `event=done` shape (UC-1 step 10).

A second integration test exercises the EC-3 fixture (`canción de prueba.mp3` — non-ASCII + spaces in path) end-to-end.

### CI orchestration
- Tier 1 runs on every PR + push; Ubuntu only, no heavy deps installed in the venv (proves the unit-test boundary).
- Tier 2 runs on every PR + push; matrix Ubuntu + macOS with full deps; per-backend skip when its library isn't available.
- Tier 3 runs on every PR + push; matrix Ubuntu + macOS; one OS, one backend each.

## Alternatives considered
- **Two-tier (unit + integration)** — what `SRS.md` §14 / `PROJECT_BRIEF.md` §8 originally sketched. Rejected: misses fake-vs-real drift on the load-bearing Protocol abstraction, which is exactly the kind of bug a small team won't catch in code review.
- **Single integration tier** — rejected: slow CI, `tiny`-model brittleness for exact-text assertions (`SRS.md` §14.1 already calls this out), can't reach 100% coverage on the segmentation-merge module without a heavy-dep install on every test run.
- **Property-based testing throughout** (`hypothesis`) — considered as an *enhancement* inside Tier 2, not a tier of its own. Worth adding if Tier 2's hand-written invariants prove fragile.

## Consequences
- **Positive:** the `WhisperBackend` Protocol's invariants are guarded against drift; unit tests stay fast (≤ 1 s) and dep-free; integration tests stay narrow and fixture-driven; coverage targets in NFR-8 are reachable without heroics. `tests/contract/` becomes the documented place to add a new behavioural assertion when a real backend exposes a new edge.
- **Negative:** more CI surface area than a two-tier setup; one extra directory under `tests/`. Acceptable for a project where the Protocol abstraction is the main testability lever.
- **Neutral:** `tests/contract/` is a less-common pattern in Python projects than in, say, microservices ecosystems where it's standard. Documented in the README's testing section so contributors know where to add what.

## Related
- ADR-0003 (WhisperBackend Protocol — the abstraction these tiers protect)
- ADR-0007 (module layout — `tests/{unit,contract,integration}/` directories)
- ADR-0011 (lazy imports — Tier 1 stays dep-free because of this)
- `SRS.md` §14, §14.1, NFR-8
- `PROJECT_BRIEF.md` §8, §9
- `SYSTEM_DESIGN.md` §3.1 (test directory layout updated)

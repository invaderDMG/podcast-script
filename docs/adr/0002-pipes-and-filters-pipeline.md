# ADR-0002: Architectural style — pipes-and-filters pipeline with explicit orchestrator class

- **Status:** Accepted
- **Date:** 2026-04-25
- **Deciders:** Solo maintainer
- **Supersedes:** —

## Context
`SRS.md` describes a strictly sequential transformation: input audio → decoded PCM → speech/music segments → transcribed speech → rendered Markdown. There are no concurrent producers/consumers, no request/response stack, no service boundaries (`PROJECT_BRIEF.md` §6 sketches the pipeline already). The transcribe phase must be memory-bounded as a function of episode length (`SRS.md` NFR-2, EC-4 ≥ 3 h), and the per-segment progress UX (`SRS.md` AC-US-3.1) requires interleaving stage logic with progress ticks.

The implementation pattern matters too: a generator-chain pipeline is idiomatic Python but awkward when later stages depend on aggregate state from earlier stages (the timestamp format `MM:SS` vs. `HH:MM:SS` is chosen *after* decode based on total duration — `SRS.md` AC-US-2.4) and when stages have side effects (`--debug` artifact writes, progress ticks, logging).

## Decision
Adopt a **pipes-and-filters** architectural style implemented as an **explicit `Pipeline` orchestrator class** (`src/podcast_script/pipeline.py`). Each stage is a separate module exposing a small typed interface (`decode.py`, `segment.py`, `render.py`, `backends/*`). The `Pipeline` class:

1. Calls each stage in order via plain method calls.
2. Holds cross-stage state (decoded duration, segment list, timestamp format choice, atomic-write temp path).
3. Owns the progress wiring and the atomic temp-then-rename of the output file.
4. Receives stage dependencies via constructor injection (so unit tests can pass mocks).

The decoded PCM is held in memory end-to-end (acceptable: ~110 MB/h mono int16 16 kHz). The transcribe phase iterates speech segments **one at a time** via the backend, ensuring transcribed-text held simultaneously is bounded to a single segment regardless of episode length.

## Alternatives considered
- **Generator/iterator chain** (`decode() | segment() | transcribe() | render()`) — rejected: cross-stage state (post-decode duration → format choice) and side effects (progress, debug writes) fight against a lazy iterator pipeline. Composes poorly with `rich.progress`.
- **Functional pipe** (`compose(render, transcribe, segment, decode)`) — rejected: hides the side effects we genuinely need; debugging a failure mid-pipe is harder than reading top-to-bottom orchestrator code.
- **Microservices / event-driven** — rejected: single process, single binary, no concurrency; the ceremony has no payoff.

## Consequences
- **Positive:** control flow is readable top-to-bottom; unit tests inject mocked stages trivially; cross-stage state has a natural home; progress wiring is centralized.
- **Negative:** `Pipeline` becomes the most complex single class in the codebase (~150–250 LOC expected); risk of becoming a "god object" if future stages don't push back. Mitigation: keep stages as separate modules with no dependency on `Pipeline`.
- **Neutral:** the `Pipeline` class is an implementation detail; the public API is the CLI (`SRS.md` §9.1).

## Related
- ADR-0003 (WhisperBackend Protocol — the pluggable stage)
- ADR-0004 (Streaming per-segment transcribe — the memory contract)
- ADR-0007 (Module layout — where stages live)
- `SYSTEM_DESIGN.md` §2.1, §2.3, §3.1
- `SRS.md` NFR-2, NFR-3, AC-US-2.4
- `PROJECT_BRIEF.md` §6

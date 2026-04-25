# ADR-0009: Backend `load()` ordering — eager, before decode

- **Status:** Accepted
- **Date:** 2026-04-25
- **Deciders:** Solo maintainer
- **Supersedes:** —

## Context
`SRS.md` AC-US-5.1 / NFR-6 require that, on first run with a missing model, the user sees a stderr notice naming the model and approximate size **within 1 second** of the tool starting the transcribe phase — and `SRS.md` US-5 frames this from the user's perspective ("so I don't think the tool has hung on a 3 GB silent download").

The pipeline has a natural ordering choice: backend `load()` (which is what triggers the model-cache lookup, and on a cache miss triggers the download notice) can happen either *before* the decode phase or *after* it. Decode is fast on small inputs (sub-second on a typical podcast) but can take many seconds on a multi-hour file.

If `load()` runs after decode, the first-run notice is delayed by however long decode takes — on a 3-hour episode that may be 10+ seconds of silent terminal, which is exactly the failure mode US-5 is preventing.

## Decision
Order the pipeline so the backend `load()` call happens **immediately after CLI validation, before decode**:

```
1. Parse argv + load config (`config.py`)
2. Validate (lang ∈ 8, ffmpeg on PATH, input readable, output absent or --force, output parent exists)
3. Select backend (platform + flag) and instantiate
4. backend.load(model, device)   ← first-run download notice fires here
5. decode → segment → transcribe-loop → render → atomic-write
```

The validation step is cheap (no IO beyond `Path.exists()` and `shutil.which("ffmpeg")`) and catches almost all invalid inputs before any model work, so the cost of an "eagerly loaded model on a doomed run" is bounded to genuine corruption cases (input passes existence/readability checks but fails inside `ffmpeg` later).

The `event=model_load_start` log line and the AC-US-5.1 stderr notice both fire from inside `load()`, so the user sees activity within milliseconds of pressing Enter (validation is sub-100 ms, then `load()` immediately announces itself).

## Alternatives considered
- **Lazy `load()` at first transcribe call** — rejected: defers the download notice past the entire decode and segment phases. On a long episode, the 1 s NFR-6 budget blows out by orders of magnitude before the notice ever lands.
- **`--prefetch-model` flag for explicit pre-warm** — rejected: adds a flag (against SRS §1.3 which limits short-flag aliases to four; even a long-only flag would be feature creep for v1). The eager-by-default ordering achieves the goal without a user-visible knob.
- **Background-thread `load()` while decode runs in main thread** — rejected: introduces concurrency the rest of the design avoids (`SYSTEM_DESIGN.md` §3.8); the gain (parallelizing load + decode) is uninteresting because load dominates wall time on first run anyway, and on subsequent runs both are fast.

## Consequences
- **Positive:** AC-US-5.1's 1 s budget is met with margin; users see model-download progress immediately on first run; the sequence diagram (SD-UC-1) becomes simpler with one canonical ordering.
- **Negative:** when input is decodable-by-existence-but-corrupt-internally (rare), we waste model-load time — bounded to one `load()` per failed run, acceptable.
- **Neutral:** the `event=backend_selected` and `event=model_load_start` log lines fire before any input-data-derived events, which is a clean log shape.

## Related
- ADR-0002 (Pipeline orchestrator — owns the call order)
- ADR-0003 (WhisperBackend — defines `load()`)
- `SRS.md` AC-US-5.1, AC-US-5.2, NFR-6, US-5
- `SYSTEM_DESIGN.md` §2.4, §3.5 SD-UC-1, §5 Risk #1

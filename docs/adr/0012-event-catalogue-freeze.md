# ADR-0012: Event catalogue freeze for v1.0.0

- **Status:** Accepted
- **Date:** 2026-04-25
- **Deciders:** Solo maintainer
- **Supersedes:** —

## Context
`SRS.md` §16.1 lists log format (NFR-10) as one of the five "format committed in writing" artifacts whose change after v1.0.0 is breaking under SemVer. `SRS.md` Risk #9 specifically flags the catalogue of `event=…` tokens emitted at default verbosity as the implicit grep-contract — users wrapping the tool in shell scripts will key off these tokens.

Before tagging v1.0.0 we need to commit to an exact set of `event=…` tokens. Adding a new token post-v1.0 is a minor (additive) change; removing or renaming one is breaking and requires a major-version bump.

`SRS.md` UC-1 step 10 already locks the shape of the `event=done` summary line; UC-2 step 3 locks the `event=model_download` shape. The rest of the catalogue draft was sketched in `SYSTEM_DESIGN.md` §2.9.

## Decision
The v1.0.0 frozen `event=…` catalogue is exactly these 22 tokens, grouped by purpose:

**Lifecycle (4):**
- `startup` — argv parsed, before any work.
- `config_loaded` — after CLI + TOML merge.
- `backend_selected` — keys: `backend=…` `device=…` `platform=…`.
- `done` — UC-1 step 10 final summary; locked shape per `SRS.md` UC-1 step 10.

**Model lifecycle (3):**
- `model_load_start` / `model_load_done` — keys: `backend=…` `model=…` `device=…` `duration_wall_s=…` (on `_done`).
- `model_download` — first-run notice; locked shape per UC-2 step 3 (`level=info event=model_download model=… size_gb=…`).

**Phase boundaries (8):**
- `decode_start` / `decode_done` — `decode_done` carries `duration_in_s=…` (the audio duration the decoder measured).
- `segment_start` / `segment_done` — `segment_done` carries `n_segments=…`.
- `transcribe_start` / `transcribe_done` — `transcribe_done` carries `n_speech_segments=…`.
- `render_done` / `write_done` — `write_done` carries `output=…`.

**Terminal errors (6, one per `PodcastScriptError` subclass plus the catch-all — see ADR-0006):**
- `usage_error` (exit 2)
- `input_io_error` (exit 3)
- `decode_error` (exit 4)
- `model_error` (exit 5)
- `output_exists` (exit 6)
- `internal_error` (exit 1)

Every error event carries `code=<exit_code>` and `cause="<short summary>"`.

**Explicitly NOT in the catalogue:**
- A per-`TranscribedSegment` `transcribe_segment` event was considered and rejected: at default verbosity it would spam stderr (one line per Whisper window across multi-thousand-segment runs), and at verbose-only it adds a token whose stability we'd later regret committing to. Per-segment progress is the progress bar's job, not the log's.

The catalogue is documented in **README.md "logfmt event catalogue"** as a small table; this ADR is the canonical record. Adding a token post-v1.0 is a minor change and updates README. Removing/renaming is breaking.

## Alternatives considered
- **Smaller catalogue** (only `startup`, `done`, error tokens) — rejected: phase-boundary events are useful for shell scripts gating on individual phases (e.g., a wrapper that times decode separately).
- **Larger catalogue** with per-`TranscribedSegment` tokens — rejected as above.
- **No commitment, document "this is what we currently emit, may change"** — rejected: SRS Risk #9 already establishes that these become a contract whether we want them to or not, the moment users start grepping. Better to commit explicitly.

## Consequences
- **Positive:** users have a stable grep target; CHANGELOG-as-contract is well-defined; an integration test (`test_event_catalogue_at_default_verbosity`) can assert exactly this token set at default verbosity, catching accidental additions/removals in CI (`SRS.md` §14.1 verification style).
- **Negative:** any future addition is a (minor) PR that touches README, CHANGELOG, and the test; small ongoing cost. Removals require a major bump.
- **Neutral:** verbose / debug verbosity may emit additional library-internal logs (`huggingface_hub`, `urllib3`); those are not part of our contract — only events emitted by `podcast_script.*` loggers count.

## Related
- ADR-0006 (typed exceptions — error event tokens 1:1 with exception classes)
- ADR-0008 (logfmt + rich — the rendering channel)
- `SRS.md` NFR-10, §16.1, Risk #9, UC-1 step 10, UC-2 step 3
- `SYSTEM_DESIGN.md` §2.9

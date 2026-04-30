# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and the project follows [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

Per `PROJECT_PLAN.md` §1.5 (the plan is frozen at v1.0), this file also
carries:

- **Sprint actuals** — per-sprint `velocity_actual=N pts` line written
  at every sprint review per §4.3 / Q12; if the forecast is missed by
  ≥ 2 pts, a one-sentence cause follows.
- **Schedule slippage** — actual tag dates differ from the §7
  projected calendar; the actual dates are recorded here, the
  projection in PROJECT_PLAN.md stays as the original baseline.
- **Risk-register churn** — new R-N entries, closed risks, or
  re-prioritisations land here rather than as in-place edits to
  PROJECT_PLAN.md §10.

The contracts treated as "format committed in writing" under SemVer
(SRS §16.1) are: output Markdown shape (§1.6), `--lang` set (§1.7),
exit-code policy (NFR-9), logfmt event catalogue (NFR-10 + ADR-0012),
and the v1.0.0 release-trigger criteria. Changes to any of these are
SemVer-major.

## [Unreleased]

### Added

#### CLI surface

- `podcast-script <input> --lang <code>` typer entrypoint with
  Levenshtein-≤-2 did-you-mean suggestions on `--lang` typos
  (AC-US-1.5; PR #4 / POD-006).
- `-o` / `--output`, `-f` / `--force`, `--model`, `--backend`,
  `--device`, `-v`, `-q`, `--debug` flags with the SRS §9.1 grammar
  (PR #4, #14, #15, #21).
- `--verbose` / `--quiet` / `--debug` are mutually exclusive at the
  cli surface (UsageError exit 2; PR #21 / POD-014).
- TOML config at `~/.config/podcast-script/config.toml` with CLI-wins
  precedence and identical `--lang` revalidation (AC-US-4.1 .. 4.4;
  PR #16 / POD-016).
- `--force` (`-f`) opt-in path for both the output Markdown and the
  `--debug` artifact directory; refuse-overwrite is the default
  (AC-US-6.1 / AC-US-6.2 / AC-US-6.3 / ADR-0015; PR #14, #15, #22).

#### Transcription pipeline

- `ffmpeg`-backed C-Decode to mono 16 kHz float32 PCM per ADR-0016
  (PR #5 / POD-007).
- Atomic temp-file + `os.replace` write per ADR-0005; failure during
  transcription leaves any prior `episode.md` intact (PR #7 /
  POD-009).
- Pipes-and-filters Pipeline orchestrator with constructor-injected
  stages per ADR-0002 (PR #8 / POD-008).
- `inaSpeechSegmenter` wrapper with TF lazy-import, label
  normalisation, and runtime suppression of three known upstream
  noise sources (Keras 3 vs the lib's Keras 2 model, numpy 2.x vs
  generator-style `np.vstack`, scipy `dct` deprecation; PR #9, #18,
  #17).
- `WhisperBackend` Protocol + concrete `FasterWhisperBackend` and
  `MlxWhisperBackend` implementations with lazy imports per
  ADR-0003 / ADR-0011 (PR #11 / POD-019, PR #13 / POD-020).
- Platform-detection rule (`arm64-darwin` → mlx-whisper, else
  faster-whisper); `--backend mlx-whisper` off Apple Silicon raises
  UsageError exit 2 per UC-1 E7 (PR #17 / POD-017).
- First-run model-download notice on cache miss within 1 s of
  process start per AC-US-5.1 / NFR-6 (PR #12 / POD-021).

#### Output / observability

- Markdown output with English music-marker pairs around every
  `music` segment, automatic `MM:SS` (< 1 h) / `HH:MM:SS` (≥ 1 h)
  selection, and `noise` / `silence` regions dropped (AC-US-2.1 ..
  2.5; PR #10 / POD-011).
- Three-phase `rich.progress.Progress` (decode / segment /
  transcribe) with per-speech-segment ticks per ADR-0010 (PR #20 /
  POD-013); disabled on non-TTY stderr per AC-US-3.2.
- Verbosity matrix mapping `-q` → ERROR, default → INFO, `-v` /
  `--debug` → DEBUG (AC-US-3.5; PR #21 / POD-014).
- 22-token frozen logfmt event catalogue per ADR-0012 — four
  lifecycle events (`startup`, `config_loaded`, `backend_selected`,
  `done`), three model-lifecycle events, eight phase-boundary
  events, six terminal-error events. The `event=done` summary line
  carries the locked UC-1 step 10 shape (`input` / `output` /
  `backend` / `model` / `lang` / `duration_in_s` /
  `duration_wall_s`; PR #19 / POD-015).
- Logfmt regex CI assertion locking NFR-10 — every stderr line from
  the project's logger is `key=value` pairs with double-quoted
  values for whitespace / `=` / `"` content (PR #24 / POD-033).

#### `--debug` artifact directory (US-7)

- `<input-stem>.debug/` next to the input contains four locked
  artifacts: `decoded.wav` (mono 16 kHz int16), `segments.jsonl`
  (one record per segment), `transcribe.jsonl` (one record per
  re-anchored speech transcription), `commands.txt` (the exact
  ffmpeg argv used; AC-US-7.1; PR #22 / POD-024).
- Incremental flush of `transcribe.jsonl` line-by-line so a mid-loop
  failure leaves the partial transcript on disk (PR #22 / POD-024).
- Refuse-without-`--force` gate on the debug directory per
  ADR-0015; mirrors US-6's output-Markdown rule (PR #22 /
  POD-025).
- AC-US-7.2 — without `--debug`, no debug dir is created and no
  `.tmp` debris survives the run.

#### Documentation

- `README.md` covering install, quickstart, output format, exit-code
  table (NFR-9), logfmt event catalogue, supported `--lang` set,
  model-size tradeoffs, accuracy caveats (EC-1 / EC-7), observed
  throughput, and the R-16 differentiator paragraphs
  (segment-then-transcribe / curated lang set / atomic-write
  contract; PR #23 / POD-036).
- `LICENSE` (MIT) at the repo root; `[project] license = "MIT"` +
  `license-files = ["LICENSE"]` in `pyproject.toml` per PEP 639
  (PR #23 review-fix).

#### Test fixtures + quality gates

- Bundled real fixture `examples/sample.mp3` — LibriVox _Las Fábulas
  de Esopo, vol. 01_ (public domain) + Musopen Chopin Prelude
  Op. 28 No. 5 (CC0 1.0). Raw sources archived in
  `examples/sources/` with SHA-256 checksums; full attribution +
  retrieval dates in `examples/CREDITS.md` (R-15 mitigation;
  PR #17 / POD-026).
- Curated `tests/fixtures/sample_tiny.md` reference output for the
  Tier 3 structural assertions per SRS §14.1 (PR #17 / POD-027).
- Tier 3 integration test running the full CLI on the real fixture
  with `--model tiny --backend faster-whisper` per ADR-0017
  (PR #17 / POD-031 scaffold).
- GitHub Actions Ubuntu + macOS-14 matrix on every push / PR per
  brief §9; the slow tier opts in via `pytest -m slow`
  (PR #6 / POD-004; slow-tier step added in PR #17).
- Tightened pytest policy: `filterwarnings = ["error"]`. Runtime
  suppression of upstream lib noise at narrow boundaries in
  `segment.py`; `HF_HUB_VERBOSITY=error` set at backend module
  load for cold-cache HF auth notice (PR #18).

### Maintainer runbook

- **After a `large-v3` model bump** — when a Dependabot PR upgrades
  `faster-whisper` or `mlx-whisper` to a release that changes
  `large-v3` weights or decode behaviour, regenerate
  `examples/sample.md` on the maintainer's reference Apple Silicon
  machine and commit alongside the lockfile bump. The `tiny`
  reference output (`tests/fixtures/sample_tiny.md`) uses
  structural-only assertions per SRS §14.1 and tolerates Whisper
  minor bumps without re-curation; `large-v3` is hand-reviewed for
  quality and may drift visibly. (R-12 mitigation, PROJECT_PLAN
  §10.1.)
- **After any change to the four `--debug` artifact filenames or
  their JSON schemas** — bump SemVer-major. The artifact contents
  are part of the v1.0 grep contract per AC-US-7.1.
- **After any change to the 22-token event catalogue** — adding a
  token is SemVer-minor (additive); removing or renaming one is
  SemVer-major (ADR-0012, SRS §16.1). Update README's catalogue
  table in the same commit.
- **After any change to the eight `--lang` codes** — adding a code
  requires a smoke-test fixture under `examples/sources/<code>/`
  and a row in the README + SRS §1.7 tables; SemVer-minor.
  Removing a code is SemVer-major (Risk #10).

### Sprint actuals

Format per `PROJECT_PLAN.md` §4.3: `velocity_actual=<N> pts` per
sprint review; if forecast missed by ≥ 2 pts a one-sentence cause
follows. Empty until the first formal sprint review.

- _(no entries yet — sprint reviews record actuals here as they
  happen.)_

### Schedule slippage

The §7 calendar dates in `PROJECT_PLAN.md` are the original
2026-04-27 baseline projection. Actual tag dates land here as they
happen (none yet — pre-v0.1.0).

### Risk-register churn

No additions, closures, or re-prioritisations since
`PROJECT_PLAN.md` v1.0 (2026-04-26). The 17 entries in §10 stand;
the headline subset (R-1, R-2, R-6, R-7, R-9) is reviewed at every
sprint planning per Q11.

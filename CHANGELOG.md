# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
and the project follows [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

Per `PROJECT_PLAN.md` §1.5 (the plan is frozen at v1.0), this file also
carries:

- **Sprint actuals** — per-sprint `velocity_actual=N` line written
  at every sprint review per §4.3 / Q12 (`N` is the integer point
  count completed); if the forecast is missed by ≥ 2 points, a
  one-sentence cause follows on the same line.
- **Schedule slippage** — actual tag dates differ from the §7
  projected calendar; the actual dates are recorded here, the
  projection in PROJECT_PLAN.md stays as the original baseline.
- **Risk-register churn** — new R-N entries, closed risks, or
  re-prioritisations land here rather than as in-place edits to
  PROJECT_PLAN.md §10.

The contracts treated as "format committed in writing" under SemVer
(SRS §16.1) are:

- §1.6 — output Markdown shape (English markers, MM:SS / HH:MM:SS).
- §1.7 — the eight-code `--lang` set.
- NFR-9 — exit-code policy (0..6).
- NFR-10 — logfmt log format (+ ADR-0012's 22-token event catalogue).
- §9.1 — CLI grammar (flag set + short aliases `-o` / `-f` / `-v` / `-q`).

Changes to any of these after v1.0.0 are breaking and warrant a
major-version bump per SemVer.

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

- Typed exception hierarchy per ADR-0006 — `PodcastScriptError` base
  + `UsageError` / `InputIOError` / `DecodeError` / `ModelError` /
  `OutputExistsError`, each carrying its `exit_code` and `event`
  class attributes (PR #2 / POD-002).
- `LogfmtFormatter` + `RichHandler` logging stack per ADR-0008 — the
  rendering channel for every log line on stderr; soft-wrap subclass
  keeps long lines on one line (PR #3 / POD-003, refined in PR #19
  / POD-015).
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
- Tier 3 PTY / no-PTY harness pinning the cli composition root's
  `stderr.isatty()` sensing — AC-US-3.1 spawns the CLI under a real
  `pty.openpty()` and asserts ANSI CSI escapes from `rich.Progress`;
  AC-US-3.2 spawns it with stderr piped and asserts no ANSI plus the
  three logfmt phase-boundary events (`decode_done`, `segment_done`,
  `transcribe_done`) as the line-per-phase fallback (PR #26 /
  POD-035).
- Tier 3 EC-3 round-trip — full CLI on an input path whose parent
  directory **and** leaf filename both carry whitespace + non-ASCII
  characters (`carpeta con espacios/canción de prueba.mp3` →
  `salida con tildes/canción de prueba.md`). Pins R-4
  (SYSTEM_DESIGN Risk #6): C-Decode's list-arg `subprocess.run`
  form (POD-007) is the load-bearing piece, and a future refactor
  to `shell=True` or string concatenation would now fail this test
  before reaching production. Asserts the locked `event=done`
  summary carries `input="…"` verbatim through logfmt's
  quoted-value branch, and that no `.tmp` debris survives the
  atomic write (ADR-0005) on a non-ASCII output parent (PR #27 /
  POD-028).
- Hypothesis property tests for the segment-merge module
  (`_normalize_to_segments` / `to_jsonl` / `Segment` in
  `src/podcast_script/segment.py`) covering NFR-3 ordering
  (AC-US-2.3), NFR-4 segmenter coverage (AC-US-2.5), the
  four-token output vocabulary, strictly-positive segment length,
  `to_jsonl` round-trip on each segment, and `Segment` frozen-ness.
  Mutation-tested locally: dropping the defensive sort in
  `_normalize_to_segments` fails 6/7 of the new properties.
  ADR-0017 §"Property-based testing throughout" was the green
  light; `hypothesis` and `pytest-cov` are dev-only, so the
  ADR-0011 lazy-import boundary and ADR-0013 no-new-runtime-deps
  invariants are unaffected (PR #28 / POD-032).
- Tier 2 contract tests under `tests/contract/` asserting the
  `WhisperBackend` Protocol invariants identically against
  `FakeBackend` plus each importable real backend
  (`FasterWhisperBackend` / `MlxWhisperBackend`) per ADR-0017 —
  empty-PCM yields empty Iterable, silence input does not raise,
  yielded `TranscribedSegment.start` values are non-decreasing,
  `transcribe()` is repeatable on a single instance after one
  `load()`, and underlying load failures wrap as `ModelError`
  (with `KeyboardInterrupt` propagating untouched per ADR-0014).
  R-14 mitigation: a synthetic-cache-miss latency contract test
  asserts the locked `event=model_download` notice fires within
  1 s of `load()` entry AND before the slow build path (the
  ordering check is what makes the contract load-bearing — the
  formal 1-s budget alone misses a notice-after-build regression).
  Real backends use the `_build_model` override seam (matching
  POD-019 / POD-020 / POD-021's Tier 1 pattern) to keep the suite
  network-free; reusable `FakeBackend` lives at `tests/fakes/whisper.py`.
  Mutation-tested locally — every invariant catches a distinct
  regression class without false positives on the others. Marked
  `pytest.mark.contract` (excluded from the default suite; opt in
  via `pytest -m contract`); a discrete CI step runs the contract
  tier on the Ubuntu + macOS-14 matrix per ADR-0017 (PR #29 /
  POD-030).
- NFR-8 100% line-coverage gate on the segment-merge module as a
  discrete CI step running `pytest --cov=podcast_script.segment
  --cov-fail-under=100` against the unit tier. The TF-only
  lazy-import paths inside `InaSpeechSegmenter` carry
  `# pragma: no cover` per ADR-0011 — production execution
  requires TensorFlow + pyannote, which is the contract surface
  Tier 2 contract tests cover (POD-030) when run with the heavy
  deps installed (PR #28 / POD-032).
- GitHub Actions Ubuntu + macOS-14 matrix on every push / PR per
  brief §9; the slow tier opts in via `pytest -m slow`
  (PR #6 / POD-004; slow-tier step added in PR #17).
- Tightened pytest policy: `filterwarnings = ["error"]`. Runtime
  suppression of upstream lib noise at narrow boundaries in
  `segment.py`; `HF_HUB_VERBOSITY=error` set at backend module
  load for cold-cache HF auth notice (PR #18).
- Tier 3 failure-injection test (`tests/integration/test_failure_
  injection.py`) — spawns the CLI as a real subprocess on
  `examples/sample.mp3`, watches stderr for the locked
  `event=transcribe_start` phase boundary (ADR-0012), then
  SIGTERMs the child mid-transcribe and asserts (a) child exited
  non-zero, (b) no Markdown landed at the resolved output path,
  (c) no `*.tmp` debris in the parent dir. Pins NFR-5 + AC-US-6.3
  end-to-end against the SRS §14.1 traceability-matrix row that
  names this test verbatim. Uncaught SIGTERM is the stronger
  failure shape than SIGINT (which ADR-0014 catches and converts
  to a clean exit-1 path that runs Python cleanup); under SIGTERM
  the only thing keeping the target path clean is the design —
  no tempfile is ever created before `atomic_write` opens one at
  the very end of `Pipeline.run`. POSIX-only (Windows skipped);
  marked `pytest.mark.slow`; CI's slow-tier step runs it on the
  Ubuntu + macOS-14 matrix per ADR-0017 (PR #32 / POD-034).
- Supply-chain hygiene per `PROJECT_BRIEF.md` §9 + §13. Two pieces,
  pairing PR-time + periodic-scan coverage of SRS §11 T2:
  - `.github/dependabot.yml` — watches the `pip` ecosystem
    (reads `pyproject.toml` + `uv.lock`) and the `github-actions`
    ecosystem (pinned action references in `.github/workflows/*`).
    Weekly cadence (Monday 06:00 UTC); minor + patch bumps batched
    into one PR per ecosystem so solo-maintainer review stays at
    one weekly window. Major bumps stay individual.
  - `.github/workflows/pip-audit.yml` — weekly cron + manual
    `workflow_dispatch` on a pinned `ubuntu-24.04` runner. Runs
    `uv export --no-dev --no-emit-project --no-hashes` to materialise
    the locked dep set, then `uvx --from pip-audit pip-audit --strict
    -r requirements.txt` to scan it against the PyPI advisory
    databases. `--strict` fails the run if any dependency can't be
    *collected* (yanked version, name-resolution failure, transient
    network glitch) so a partial scan can't pass silently; vuln
    detection itself is unconditional and exits non-zero on any
    finding. No new dev dep — pip-audit runs in `uvx`'s isolated
    venv per ADR-0013 (PR #33 / POD-005).

### Changed

- Test tree split by tier per ADR-0017 §3.1. The 16 Tier 1 test
  modules now live under `tests/unit/`; the three Tier 3 test modules
  live under `tests/integration/`; `tests/contract/` is unchanged.
  `pytest tests/unit` selects exactly Tier 1 by path (no marker
  negation needed); `pytest tests/integration -m "slow or not slow"`
  selects Tier 3. Default suite count + outcomes byte-identical to
  pre-reorg (252 / 21 / 5 across the three tiers). NFR-8
  segment-merge coverage gate in `.github/workflows/ci.yml`
  repointed to `tests/unit/test_segment{,_property}.py`. Three Tier 3
  modules' `REPO_ROOT` constants gained one extra `.parent` to
  preserve the path-up traversal across the deeper directory; without
  that fix the slow tier would have skipped silently rather than run
  (PR #30 / POD-029).

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
- **After any change to the Markdown output shape** (English music
  markers, `MM:SS` / `HH:MM:SS` timestamp format, blockquote +
  speech-line interleave, `noise` / `silence` dropped) — bump
  SemVer-major. The output shape is the user-facing contract per
  SRS §1.6 + §16.1; downstream tooling parses the literal byte
  sequences (e.g. `> [<ts> — music starts]`).
- **After any change to the CLI grammar** — the locked flag set,
  argument order, and short aliases `-o` / `-f` / `-v` / `-q` per
  SRS §9.1 / §16.1 are part of the format contract. Adding a flag
  is SemVer-minor (additive); changing or removing one, renaming a
  short alias, or relaxing the verbosity-flag mutual-exclusion rule
  is SemVer-major.

### Sprint actuals

Format per `PROJECT_PLAN.md` §4.3 / §1.4 glossary:
`velocity_actual=<N>` (integer points completed) per sprint review;
if the forecast was missed by ≥ 2 points a one-sentence cause
follows on the same line. Empty until the first formal sprint
review.

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

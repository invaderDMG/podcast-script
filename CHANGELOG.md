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

### Fixed

- **Issue #45** — `MlxWhisperBackend._build_model` now resolves bare
  Whisper shortnames (`tiny`, `base`, `small`, `medium`, `large-v3`,
  `large-v3-turbo`) to their canonical `mlx-community/whisper-<shortname>`
  HuggingFace repo id before delegating to
  `mlx_whisper.load_models.load_model`. Previously the bare shortname
  was passed verbatim, causing `RepositoryNotFoundError: 401 Client
  Error … Repository Not Found for url:
  https://huggingface.co/api/models/large-v3/revision/main` on every
  fresh-cache mlx run with `--model large-v3` (the dogfooder default).
  The new `_resolve_repo_id` helper is idempotent on already-qualified
  repo ids and local filesystem paths, so power-user overrides
  (`--model mlx-community/whisper-large-v3-q4`, `--model /path/to/local`)
  pass through unchanged. Aligns with `_is_cached`'s `/whisper-{model}`
  anchor so cache lookup and download-resolve agree on the same
  shortname (`src/podcast_script/backends/mlx.py`).
- **Issue #44** — `FasterWhisperBackend` constructs `WhisperModel` with
  `compute_type="auto"` instead of the lib default `"default"`. With
  `"default"`, CTranslate2 inferred the compute type from the saved
  Systran weights (`float16`), then fell back transparently to a
  device-supported type AND emitted `[ctranslate2] [warning] The
  compute type inferred from the saved model is float16, but the
  target device or backend does not support efficient float16
  computation` directly to stderr from the C++ layer — slipping past
  the logfmt-only NFR-10 promise on every macOS arm64 CPU run.
  `"auto"` skips the inference step entirely and picks the most
  efficient natively-supported type (typically `int8` on CPU,
  `float16` on CUDA), eliminating the warning without changing
  transcription quality (`src/podcast_script/backends/faster.py`).

### Changed

- `tests/contract/conftest.py` now passes the bare `"tiny"` shortname
  to `MlxWhisperBackend.load(...)` (matching the faster-whisper
  sibling) — the workaround constant `_MLX_TINY_MODEL =
  "mlx-community/whisper-tiny"` and its tracking comment are gone now
  that issue #45 is fixed.

## [0.1.1] - 2026-05-02

Patch release per SemVer 2.0.0 §4. No API changes; delta is the
four PRs merged between v0.1.0 and v0.1.1: dogfooding guide,
Dependabot action bumps, and Dependabot config tightening to
prevent the closed PR #36's proposal class from recurring. The
five `SRS.md` §16.1 contracts (output Markdown shape, 8-code
`--lang` set, exit codes, logfmt format + 22-token catalogue, CLI
grammar) are untouched. Cut to give invited dogfooders a real
pinned tag with `docs/DOGFOODING.md` included — the v0.1.0 tag
predates the guide.

### Added

- `docs/DOGFOODING.md` — invitation guide for the v0.1.0 → v1.0.0
  dogfooder phase per `PROJECT_PLAN.md` §8 / Q7. Covers prerequisites,
  step-by-step install + smoke test + run-on-own-audio flow, an
  evaluation checklist (transcript quality, music markers, output
  format, UX), GitHub Issues feedback templates (env block + bug-shaped
  vs. quality-shaped reports), the documented v1 limitations that are
  *not* bugs (so dogfooders don't burn cycles on EC-1 / model-size /
  no-batch / atomic-rename-no-partial), the Q7 acceptance bar
  reflected as pass/fail, and a copy-paste-ready DM template the
  maintainer can use to invite people. README has a one-paragraph
  pointer between "Development" and "License" so an invited dogfooder
  who lands on the README first finds the guide (PR #42).

### Changed

- `actions/checkout` bumped v4 → v6 in both CI workflows
  (`.github/workflows/ci.yml`, `.github/workflows/pip-audit.yml`).
  First Dependabot grouped weekly PR after the v0.1.0 cut; major
  bump so it landed individually rather than under the
  `pip`/`actions` minor + patch group per the rules in
  `.github/dependabot.yml` (PR #34).
- `astral-sh/setup-uv` bumped v6 → v7 in both CI workflows. Same
  pathway as `actions/checkout` above; rebased against
  post-PR-#34/#38 main before merge so the matrix legs ran on
  `ubuntu-24.04` (not the pre-pin `ubuntu-latest`) (PR #35).
- Tightened the `numpy` Dependabot ignore in
  `.github/dependabot.yml`: added `versions: [">=2.0"]` alongside
  the existing `update-types: version-update:semver-major` filter.
  The `update-types` filter only catches version-update PRs (i.e.
  bumping the lockfile from 1.26.x to 2.x); it doesn't catch
  *requirement-update* PRs (broadening `pyproject.toml`'s
  `numpy<2.0` cap to `<3.0`) — which Dependabot proposed shortly
  after v0.1.0 (closed PR #36). The `versions` filter applies to
  both update modes, making the ignore defence-in-depth. Drop the
  `versions` line at the same moment `inaspeechsegmenter` unpins
  to ≥ 0.8.x with Apple Silicon support; the existing
  `inaspeechsegmenter` ignore tracks the same trigger (PR #41,
  refs closed PR #36).

### Maintenance

- Closed `PR #36` (Dependabot proposal to broaden `numpy>=1.26,<2.0`
  to `<3.0`) without merging — the `<2.0` cap is deliberate per
  `pyproject.toml:14-19` (inaSpeechSegmenter 0.7.6 incompatibility
  with numpy 2.x). The `numpy` ignore tightening above (PR #41)
  prevents the same proposal from recurring.

## [0.1.0] - 2026-05-02

First usable release per `PROJECT_BRIEF.md` §16 — the test pyramid
is green on Ubuntu + macOS-14, the README quickstart works against
the bundled `examples/sample.mp3` LibriVox + CC0 fixture, and the
five v1.0 contracts (`SRS.md` §16.1 — output Markdown shape,
8-code `--lang` set, exit-code policy NFR-9, logfmt log format
NFR-10 + 22-token event catalogue, CLI grammar §9.1) are all
shipped. The five contracts are **first locked in writing** at this
tag; per the file header above and `SRS.md` §16.1, SemVer-major
attaches at `v1.0.0`. Until then, contract changes between `0.x`
releases are minor-bumps under SemVer 2.0.0 §4.

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
- `docs/ARCHITECTURE.md` — the maintainer-facing front-door
  one-pager mandated by SRS §16.2 / Q20. Covers exactly the four
  load-bearing invariants (segment-then-transcribe pipeline;
  `WhisperBackend` Protocol + platform-detection rule;
  segmenter-covers / renderer-drops noise + silence;
  atomic-write via temp + rename) with each bullet naming the
  failure mode the choice avoids and pointing at the relevant
  ADR. No "rejected alternatives" appendix per SRS §1.3 Won't
  list — that material stays in the individual ADRs under
  `docs/adr/`. 176 lines; the rest of v1 maintainer-facing docs
  surface (README, CHANGELOG, ADRs) is already in place
  (PR #37 / POD-037).

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
- Major-version caps on the three open-bound runtime deps in
  `pyproject.toml` — `faster-whisper>=1.2,<2.0`,
  `huggingface_hub>=1.12,<2.0`, `mlx-whisper>=0.4,<0.5` (the 0.x
  one is capped at the next minor since SemVer 0.x treats minors
  as breakable). Lower bounds bumped to the currently-locked
  minor so a downstream venv can't silently downgrade below what
  CI tests against. R-14 / R-17 mitigation — Dependabot's
  grouped weekly PR brings minor + patch upstream bumps under
  the cap; major bumps stay individual review per the dependabot
  config landed in PR #33. `inaspeechsegmenter==0.7.6` and
  `numpy>=1.26,<2.0` already had bounds and are unchanged
  (PR #38).
- CI matrix Ubuntu runner pinned: `ubuntu-latest` →
  `ubuntu-24.04` in `.github/workflows/ci.yml`. R-13-shaped
  Linux-side companion to the existing `macos-14` pin and to
  the `ubuntu-24.04` already in `pip-audit.yml` (PR #33). Both
  pins block the silent-CI-rollover failure mode where a fresh
  GitHub-hosted image lands and breaks an existing build
  mid-sprint (PR #38).

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
follows on the same line. Forecast was 8 sub-pts/sprint for
SP-1..SP-7 and 5–7 for SP-8 per `PROJECT_PLAN.md` §6.

- **SP-1** velocity_actual=8 — US-1 partial (POD-001 skeleton,
  POD-002 errors, POD-003 logging baseline, POD-006 CLI, POD-007
  decode, POD-009 atomic write) + POD-004 GitHub Actions baseline
  CI shipped per scope (PR #2..#7 + initial commit `5981e5d`).
  SPK-1 (TF + MLX + faster-whisper combined install on macOS-14)
  resolved off-velocity by the CI matrix coming up green on the
  first run.
- **SP-2** velocity_actual=8 — US-1 finished (POD-008 Pipeline
  orchestrator) + US-2 (POD-010 segmenter, POD-011 render) per
  scope (PR #8..#10).
- **SP-3** velocity_actual=8 — US-5 partial (POD-018 Protocol,
  POD-019 faster-whisper, POD-021 first-run notice; PR #11..#12)
  + POD-029 Tier 1 unit-test baseline (4 of 5 sub-pts; the
  trimmed 1 sub-pt landed in SP-6 as planned at sprint scoping
  per `PROJECT_PLAN.md:270`, not slippage). POD-026/POD-027/
  POD-031 (originally SP-7 scope) also landed early in PR #17 —
  freed capacity later in the sprint and removed schedule risk
  from SP-7.
- **SP-4** velocity_actual=8 — US-5 finished (POD-020 mlx-whisper)
  + US-4 (POD-016 Config + POD-017 select_backend) + US-6
  (POD-022 refuse-overwrite + POD-023 force opt-in) + POD-030
  Tier 2 contract-tests baseline (FakeBackend + Protocol-invariant
  runner — PR #13..#16; POD-017 + POD-030 baseline rolled into
  PR #17). macOS-14 CI green from this sprint forward.
- **SP-5** velocity_actual=8 — US-3 (POD-013 progress bar +
  POD-014 verbosity matrix + POD-015 22-token event-catalogue
  freeze; PR #19..#21) + POD-003' full ADR-0008 wiring (refined
  in PR #19) + POD-033 logfmt-regex CI assertion (PR #24) +
  POD-035 PTY/no-PTY harness (PR #26). The full UX surface
  shipped: rich progress on TTY, line-per-phase on pipe,
  catalogue frozen.
- **SP-6** velocity_actual=8 — US-7 (POD-024 `--debug` artefact
  dir + POD-025 refuse-without-`--force`; PR #22 bundled both)
  + POD-029 finish (`tests/{unit,integration}/` reorg per ADR-0017
  §3.1 + the stale-ref docstring follow-up; PR #30 + PR #31)
  + POD-030 finish (real-backend contract tests + R-14 huggingface
  1-s latency invariant; PR #29) + POD-032 property tests + 100%
  segment-merge coverage gate (PR #28) + POD-034 failure-injection
  Tier 3 (kill-mid-transcribe pins NFR-5 + AC-US-6.3 end-to-end;
  PR #32). Test pyramid solid; M-6 reached.
- **SP-7** velocity_actual=8 — POD-036 README (install +
  quickstart + format + exit-code table + 22-token event
  catalogue + R-16 differentiator paragraphs; PR #23) + POD-028
  EC-3 round-trip (`carpeta con espacios/canción de prueba.mp3`
  end-to-end; PR #27). POD-026/POD-027/POD-031 already shipped
  early in SP-3's PR #17 — those stayed accounted for under SP-3
  but the SP-7 deliverable (real fixture + CI-green Markdown
  round-trip + publishable README) was reachable end-to-end at
  M-7. Dogfooder phase per Q7 still pending — gated on v0.1.0
  tag (POD-039).
- **SP-8** _(in progress)_ — landed so far: POD-005 Dependabot
  + pip-audit cron (PR #33), POD-037 ARCHITECTURE.md (PR #37),
  R-13/R-14/R-17 dep + runner version pins (PR #38), POD-038
  sprint actuals (this PR). Pending: POD-039 v0.1.0 tag,
  POD-040 v1.0.0 tag (gated on dogfooder feedback per Q7).
  Final `velocity_actual` recorded at sprint close, alongside
  the v1.0.0 tag.

### Schedule slippage

The §7 calendar dates in `PROJECT_PLAN.md` are the original
2026-04-27 baseline projection. Actual tag dates land here as they
happen.

- **v0.1.0 — actual 2026-05-02; projected M-7 / end of SP-7
  (2026-08-02 per `PROJECT_PLAN.md:327`).** Released ahead of
  schedule; the eight-sprint × two-week projection assumed
  part-time evening/weekend cadence per §1.3, but actual delivery
  pace was ~6 calendar days of compressed work. The projection
  stays as the original baseline per §1.5; this entry is the
  variance record. v1.0.0 tag (POD-040) is still gated on
  dogfooder feedback per Q7 — the calendar acceleration does not
  shorten the human review window.
- **v0.1.1 — actual 2026-05-02; not projected.** Same-day patch
  release after v0.1.0; the §7 calendar table doesn't enumerate
  patch tags (only major sprint milestones M-1..M-8), so this is a
  no-projection variance — recorded for completeness rather than
  schedule analysis. Cut to bundle the dogfooding guide
  (PR #42) + Dependabot triage (#34, #35, #41) into a tag the
  guide URL actually resolves under, since the v0.1.0 tag predates
  the guide commit. No CI gate change vs. v0.1.0.

### Risk-register churn

No structural additions, closures, or re-prioritisations since
`PROJECT_PLAN.md` v1.0 (2026-04-26). The 17 entries in §10 stand;
the headline subset (R-1, R-2, R-6, R-7, R-9) is reviewed at every
sprint planning per Q11.

Plan-text inconsistencies surfaced during execution (these are
*documentation* nits, not register changes; recorded here per §1.5
because the plan is frozen and won't be edited):

- **`PROJECT_PLAN.md:148` POD-005 line reads "(mitigation for SRS
  T2 / R-1)".** The "T2" attribution is correct (`SRS.md` §11 T2
  is dependency supply chain). The "R-1" attribution is **not** —
  R-1 in `PROJECT_PLAN.md` §10 is "TF (via inaSpeechSegmenter) +
  MLX + faster-whisper combined install on Apple Silicon may
  conflict", not supply chain. The actual supply-chain risks
  POD-005 mitigates are upstream of R-1's framing — the
  Dependabot + pip-audit setup landed in PR #33 maps to SRS T2
  alone. (Surfaced by self-review on PR #33; deferred to
  v0.1.0 PR per §1.5 plan-governance — recorded here, not as
  an edit to PROJECT_PLAN.md.)

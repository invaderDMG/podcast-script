# Project Plan — v0.4  (confidence: 92%)

## Changelog
- v0.4 (2026-04-26) — resolved Q10–Q13. Pre-SP-1 readiness = "just go" (Q10, kept default — tooling is maintainer's local responsibility, SP-1 uses any MP3 stand-in, SPK-1 in parallel). Risk-review policy = **review all 17 risks at every sprint planning (~10 min)** with the five high-priority entries (R-1/R-2/R-6/R-7/R-9) flagged as headline items (Q11 — multi-check: user ticked both the 5-entry subset AND the "all 17" superset; resolved by adopting the more inclusive scope). Velocity-refinement substitute confirmed = per-sprint `velocity_actual=N + cause` CHANGELOG line (Q12, kept default). Round 4 is a close-out tightening pass; declare v1.0 next iteration (Q13, kept default). Updated §10 with risk-review policy block; updated §11 ceremony table to fold the 10-minute all-17 risk scan into planning. Confidence climbs to 92% across the board: Team/cadence 90→92, DoR/DoD 85→90, Estimation scale 85→92, Task breakdown 85→92, Estimates 90→95, Velocity 85→92, Sprint comp 85→92, Roadmap 85→92, User-testing 85→92, Dependencies 85→92, Risks tech 90→95, Risks ops 85→92, Risks biz 85→92, Mitigation ownership 80→90, Ceremony 80→92.
- v0.3 (2026-04-26) — resolved Q6–Q9: bulk-accepted seven story estimates as final v0.2 baseline (Q6, kept default — **dropped `(provisional)` markers** in §4.2 + §5); confirmed user-testing cadence self/dogfoot/public (Q7, kept default — expanded §8 into a self-contained phase table); ceremonies **lightened to planning + review only for SP-1..SP-3, retro added from SP-4 onward** (Q8, moved off recommendation — §11 rewritten + §4.3 velocity-refinement substitute added: per-sprint `velocity_actual=N` line in CHANGELOG); risk register grew from 11 → **17** entries (Q9, **all six candidates ticked including R-16 and R-17**) — added R-12 (large-v3 vs tiny output divergence), R-13 (macOS runner image bumps), R-14 (huggingface_hub API evolution), R-15 (LibriVox+CC0 sourcing fragility), R-16 (competing OSS tool adoption risk), R-17 (faster-whisper API shape change). Confidence bumps: Estimates 60→90, User-testing 30→85, Ceremony 30→80, Risks tech 75→90, Risks ops 50→85, Risks biz 60→85, Mitigation ownership 70→80, Task breakdown 80→85, Velocity 80→85, Sprint comp 80→85, Roadmap 80→85, Dependencies 80→85.
- v0.2 (2026-04-26) — resolved Q1–Q5: sprint length **2 weeks** (Q1, default), velocity **8 pts/sprint** (Q2, default), SP-1 **thin-stub end-to-end** (Q3, default), DoD = **merged + CI matrix + smoke + AC + docs** (Q4, default), task ID convention = **`POD-NNN` zero-padded 3-digit** (Q5 — moved off recommendation; user picked Other). **Bulk-renamed every task ID `T-N` → `POD-NNN`** across §5/§6/§9/§10. **POD-012 deliberately retired** (no `T-12` was ever assigned in v0.1; gap preserved per "IDs never get reused" rule). Bumped confidence on Team/Cadence (70→90), DoR/DoD (50→85), Velocity (40→80), Sprint composition (60→80), Roadmap (65→80), Estimation scale (75→85), Task breakdown (70→80), Mitigation ownership (30→70 — every owner is the solo maintainer, which is trivially the answer for this project shape).
- v0.1 (2026-04-26) — initial draft seeded from `SRS.md` v1.0, `SYSTEM_DESIGN.md` v1.0 (17 Accepted ADRs), `PROJECT_BRIEF.md` v1.0. Decomposed US-1..US-7 into 40 tasks (T-1..T-40) using the §3.1 module layout as the structural backbone. Provisional Fibonacci estimates per story. 8 sprints drafted (SP-1..SP-8) with one testable deliverable per sprint, ordered by the architectural dependency chain (decode → segment → backend → progress → debug → polish). Risk register seeded from SRS §15 + SYSTEM_DESIGN §5; added solo-maintainer-specific operational risks. SPK-1 added for TF+MLX combined install validation (SRS Risk #5 / SYSTEM_DESIGN Risk #3, still open).

## Confidence by area
- Team & cadence: 92%
- Definition of Ready / Done: 90%
- Estimation scale & calibration: 92%
- Task breakdown: 92%
- Estimates (Fibonacci): 95%
- Velocity & capacity: 92%
- Sprint composition: 92%
- Release roadmap & deliverables: 92%
- User-testing cadence: 92%
- Dependencies & critical path: 92%
- Risks: technical: 95%
- Risks: operational: 92%
- Risks: business: 92%
- Mitigation ownership: 90%
- Ceremony cadence & grooming: 92%

## 1. Inputs & assumptions

### 1.1 Source documents
- SRS: `SRS.md` v1.0 (2026-04-25, 93% confidence) — 7 user stories US-1..US-7, MoSCoW priorities locked, 14 acceptance-criteria sets, NFR-1..NFR-10, 6-entry edge-case set EC-1/2/3/4/7/10, 10-entry risk register §15.
- System design: `SYSTEM_DESIGN.md` v1.0 (2026-04-25, 97% confidence) + 17 Accepted ADRs in `docs/adr/` (immutable as of 2026-04-25). Module layout in §3.1 dictates the package structure used as the task backbone here.
- Project brief: `PROJECT_BRIEF.md` v1.0 (2026-04-25, 91% confidence) — solo maintainer, MIT, public GitHub repo, no deadline, released as ready.

### 1.2 Locked-in constraints (do not re-litigate)
- **Solo maintainer**: 1 engineer (no peers, no required reviewers, no Scrum Master role).
- **No deadline**: released as ready; v0.1.0 = first usable, v1.0.0 = first tagged release whose CI passes against the SRS (SRS §16.1).
- **Tech stack frozen**: Python 3.12+, `uv` + `hatchling`, `typer`, `rich`, `ffmpeg` (system dep), `inaSpeechSegmenter`, `faster-whisper` + `mlx-whisper`, `huggingface_hub`, `numpy`/`soundfile`. **No additional runtime deps** (ADR-0013).
- **CLI grammar locked**: SRS §9.1.
- **Output format locked**: SRS §1.6 (English markers, MM:SS auto / HH:MM:SS auto).
- **Supported `--lang` set locked**: 8 codes — es/en/pt/fr/de/it/ca/eu (SRS §1.7).
- **Exit-code policy locked**: 0/1/2/3/4/5/6 (NFR-9).
- **Log format locked**: logfmt key=value (NFR-10) + 22-token event catalogue frozen for v1.0.0 (ADR-0012).
- **Test fixture spec locked**: `examples/sample.mp3` = LibriVox ~60 s + CC0 music bed at 25–35 s (SRS §14.1).
- **Three-tier test strategy**: Tier 1 unit / Tier 2 contract / Tier 3 integration (ADR-0017).
- **CI**: GitHub Actions, Ubuntu + macOS matrix on every PR + push (brief §9, free for public repos).
- **Sprint length**: 2 weeks (Q1, resolved in v0.2).
- **Velocity forecast**: 8 pts/sprint (Q2, resolved in v0.2; refined to actuals after SP-1).
- **DoD**: merged to `main` + CI matrix green on Ubuntu + macOS + smoke test on `examples/sample.mp3` + AC verified in tests + README/CHANGELOG updated if user-facing (Q4, resolved in v0.2).
- **Task ID convention**: `POD-NNN`, zero-padded 3-digit, globally numbered, retired-IDs-not-reused (Q5, resolved in v0.2).
- **Story estimates**: US-1=8, US-2=5, US-3=5, US-4=3, US-5=5, US-6=2, US-7=3 (Q6, resolved in v0.3 — final, no longer provisional).
- **Ceremonies (lightened)**: planning + review only for SP-1..SP-3; retro added from SP-4 onward (Q8, resolved in v0.3).
- **Risk-review policy**: review **all 17 risks** at every sprint planning (~10 min); five high-priority entries (R-1, R-2, R-6, R-7, R-9) are headline items (Q11, resolved in v0.4).
- **Velocity-refinement substitute**: per-sprint `velocity_actual=N + cause-if-missed` line written to CHANGELOG at every sprint review (Q12, resolved in v0.4).

### 1.3 Working assumptions (challenge these)
- **Solo dev capacity**: ~8 points/sprint on 2-week sprints, modeling part-time evening/weekend availability with ~0.4 effective focus factor. Forecast revised to actuals after SP-1.
- **Calendar projection**: SP-1 starts week of 2026-04-27. 8 sprints × 2 weeks = ~16 weeks → v1.0.0 tag projected around 2026-08-16. **Calendar dates are projections, not commitments.**
- **CI minutes**: GitHub Actions free-tier on public repos is unlimited; treating it as such.
- **No external pilot users in v0.x**: the maintainer self-tests sprint deliverables until v0.1.0 is tagged. External user testing happens at SP-7 (1–2 dogfooders) and post-v1.0.0 (public via GitHub Issues).

### 1.4 Glossary
- **MoSCoW priority**: from SRS §13. Must = required for v1.0.0; Should = nice-to-have for v1.0.0; Could = explicitly empty per SRS §13; Won't = deferred.
- **Tier 1 / Tier 2 / Tier 3 tests**: ADR-0017 — unit (pure logic + fakes), contract (Protocol invariants vs fakes AND real backends), integration (full CLI on `examples/sample.mp3`).
- **Spike (SPK-N)**: time-boxed investigation, sized in points but **off-velocity** (does not count toward delivery throughput).
- **Story-level "Must" / "Should"**: inherited from SRS §13 MoSCoW; `Must` stories block v1.0.0, `Should` stories may slip post-v1.0.0 if velocity disappoints.
- **`POD-NNN`**: project-scoped task ID (Q5). Zero-padded 3-digit; globally numbered; retired IDs are not reused (e.g. POD-012 was retired in the v0.1 → v0.2 rename and stays unassigned).
- **`velocity_actual=N`**: per-sprint logfmt-style line written to CHANGELOG at sprint review (Q8 + Q12 substitute) — captures completed points + a one-sentence cause if the forecast was missed by ≥ 2 pts.
- **Headline risk**: a risk in the high-priority subset (R-1, R-2, R-6, R-7, R-9) that gets explicit attention at every sprint planning's risk review. All other risks are still scanned each planning per Q11 but only require action on their listed re-assess trigger.

## 2. Team & cadence

- **Team**: 1 maintainer (solo). Roles collapsed: maintainer = developer + reviewer + release manager + product owner.
- **Sprint length**: **2 weeks** (Q1 resolved).
- **Working calendar**: maintainer's local time zone (Europe/Madrid, inferred from name + email domain). No declared PTO captured yet.
- **Ceremonies**: see §11 for full rules.
  - SP-1..SP-3: planning + review only; **no retro**; ad-hoc grooming.
  - SP-4 onward: planning + review + retro added; ad-hoc grooming.
  - Risk review at every planning covers all 17 entries (~10 min — Q11 resolved).

## 3. Definition of Ready / Definition of Done

### 3.1 Definition of Ready (DoR)
A story is ready to enter a sprint when:
- It has acceptance criteria in Given-When-Then form (SRS already provides this for US-1..US-7).
- It has a final Fibonacci estimate (Q6 resolved this for all seven user stories; new stories require explicit estimation).
- All dependencies — preceding stories, ADRs, source fixtures — are in `Done` or explicitly marked unblocking.
- No open question would change the AC mid-sprint (the SRS `Resolved questions` audit trail is the source of truth here).

### 3.2 Definition of Done (DoD) — resolved Q4
A story is done when:
- Code merged to `main` via squash from a feature branch.
- Relevant tests added at the appropriate tier (Tier 1/2/3 per ADR-0017); `pytest` green locally and in CI.
- `ruff check`, `ruff format --check`, `mypy --strict` all pass (NFR-8).
- GitHub Actions matrix (Ubuntu + macOS) green.
- Smoke test on `examples/sample.mp3` (or its sprint-equivalent stub) succeeds end-to-end.
- All ACs from the SRS for that story verified in test code.
- README / CHANGELOG updated if the change is user-facing.
- Coverage target maintained: ≥ 80% lines overall, 100% on the segmentation-merge module (NFR-8).

## 4. Estimation

### 4.1 Scale
Fibonacci: **1, 2, 3, 5, 8, 13, 21**. Upper bound for a single committable story: **8** (resolved by SP-1 sizing in Q3). Anything 13+ must be split or preceded by a spike.

### 4.2 Calibration anchor — final
**US-6 (Refuse-overwrite without `--force`) = 2 points** as the anchor. Reasoning: validation in C-CLI + atomic invariant via `os.replace` (already required by NFR-5) + the `--force/-f` flag + 4 ACs (AC-US-6.1..6.4). Well-bounded, ~1 day work, no architectural unknowns. Every other story is sized relative to this and **all seven are final** (Q6 resolved):

| Story | Points | Rationale |
|-------|--------|-----------|
| US-6  | **2**  | Anchor — validation + atomic invariant + 4 ACs. |
| US-4  | **3**  | TOML parse + dataclass merge + lang revalidation; small but spans modules. |
| US-7  | **3**  | Strictly more than US-6 — 3 file-type emissions + dir-pre-existence policy mirroring US-6. |
| US-2  | **5**  | Segmenter wrapper + render with two timestamp modes + ordering invariant. |
| US-3  | **5**  | rich Progress + LogfmtFormatter + non-TTY fallback + verbosity matrix. |
| US-5  | **5**  | Two backends mirrored + first-run notice within 1 s + cache-miss detection. |
| US-1  | **8**  | Spans full pipeline (CLI, decode, lang validation, end-to-end orchestration); the spine that everything else hangs off. |

### 4.3 Velocity forecast — resolved Q2
- **Initial forecast**: 8 points/sprint. Source: 1 engineer × 0.4 effective focus (part-time evenings/weekends) × 10 working days × ~2 points/effective-day-of-actual-coding ≈ 8.
- **Refinement policy**: yesterday's-weather after SP-1; switch to a 3-sprint rolling average after SP-3. Calendar dates in §7 re-projected each sprint review.
- **Capacity caveat**: this forecast is for net coding capacity. Spikes (SPK-1) are **off-velocity** by design (ADR-0017 + skill convention).
- **Velocity refinement during the no-retro period (SP-1..SP-3, per Q8)**: even without retros, "yesterday's-weather" forecasting still works mechanically — SP-2's forecast = SP-1's actual completed points. To preserve the qualitative lessons retros would normally capture, **every sprint review records a one-line `velocity_actual=N` entry in `CHANGELOG.md`** plus a one-sentence cause if the forecast was missed by ≥ 2 pts (Q12 confirmed). From SP-4 onward the retro re-introduces a fuller start/stop/continue note.

## 5. Task breakdown

Convention: **globally-numbered `POD-NNN`**, zero-padded 3-digit (Q5 resolved). Sub-points (`1`, `2`, `3`) used for tasks; the parent story carries the canonical Fibonacci estimate (Q6 resolved — final, no longer provisional). Cross-cutting infrastructure tasks (POD-001..POD-005, POD-026..POD-040) live outside individual stories but are scheduled into specific sprints in §6. **Retired IDs stay retired** — POD-012 was deliberately not assigned in the v0.1 → v0.2 rename.

### Cross-cutting infrastructure tasks (no single US home)

- **POD-001** — Project skeleton: `uv init`, `pyproject.toml` with hatchling backend, `src/podcast_script/` layout per ADR-0007, `ruff` + `mypy --strict` config, baseline `__init__.py` (1 sub-pt) — maintainer
- **POD-002** — `errors.py`: `PodcastScriptError` base + 5 subclasses with `exit_code` and `event` class attributes per ADR-0006 (1 sub-pt) — maintainer
- **POD-003** — `logging_setup.py`: `LogfmtFormatter` + `RichHandler` wired through `Progress.console` per ADR-0008 (initial cut: 1 sub-pt; full event-catalogue wiring in POD-015) — maintainer
- **POD-004** — GitHub Actions `ci.yml`: Ubuntu + macOS matrix, `astral-sh/setup-uv`, `ruff` + `mypy --strict` + `pytest` steps per brief §9 (2 sub-pt) — maintainer
- **POD-005** — Dependabot config + `pip-audit` weekly cron (mitigation for SRS T2 / R-1) (1 sub-pt) — maintainer

### US-1 — Transcribe a single Spanish episode to Markdown  (Must, **8 points**)
**Sprint:** SP-1 (skeleton/decode) + SP-2 (pipeline/render)
**Linked AC:** AC-US-1.1, AC-US-1.2, AC-US-1.3, AC-US-1.4, AC-US-1.5
**Linked features:** F1, F8
**Tasks:**
- **POD-006** — `cli.py`: `typer` entrypoint + `--lang` curated-set validation + did-you-mean (Levenshtein ≤ 2) + `UsageError` → exit 2 (F8) (2 sub-pt) — maintainer
- **POD-007** — `decode.py` (C-Decode): `subprocess.run` with list args (EC-3 paths), canonical `ffmpeg -f f32le -ar 16000 -ac 1` per ADR-0016, `commands.txt` capture, `DecodeError` → exit 4 (3 sub-pt) — maintainer
- **POD-008** — `pipeline.py` (C-Pipeline) orchestrator: validate → load → decode → segment → transcribe-loop → render → atomic-write per ADR-0002 + ADR-0009 + ADR-0004 streaming contract (3 sub-pt) — maintainer
- **POD-009** — Atomic write via `tempfile.NamedTemporaryFile(dir=output.parent)` + `os.replace` per ADR-0005 (1 sub-pt) — maintainer
**Notes:** US-1 is the spine; SP-1 ships with stub segmenter + stub backend so the orchestrator + decode + atomic write can be exercised end-to-end before the heavy ML deps land.

### US-2 — See music segments annotated with timestamps  (Must, **5 points**)
**Sprint:** SP-2
**Linked AC:** AC-US-2.1, AC-US-2.2, AC-US-2.3, AC-US-2.4, AC-US-2.5
**Linked features:** F2
**Tasks:**
- **POD-010** — `segment.py` (C-Segment): `inaSpeechSegmenter` wrapper, lazy TF import inside `Segmenter.load()` per ADR-0011, `segments.jsonl` emit under `--debug` (3 sub-pt) — maintainer
- **POD-011** — `render.py` (C-Render): pure function `render(segments, transcripts, fmt) -> str`, English markers (AC-US-2.2), `MM:SS` < 1 h / `HH:MM:SS` ≥ 1 h auto (AC-US-2.4), drop noise/silence (AC-US-2.5 + NFR-4) (2 sub-pt) — maintainer
**Notes:** Property test on the segment-merge module covers NFR-3 ordering invariant and 100% line coverage requirement (NFR-8); test goes in POD-032 (SP-6). **POD-012 retired** (never assigned).

### US-3 — Get progress feedback during long episodes  (Must, **5 points**)
**Sprint:** SP-5
**Linked AC:** AC-US-3.1, AC-US-3.2, AC-US-3.3, AC-US-3.4, AC-US-3.5
**Linked features:** F5, F9
**Tasks:**
- **POD-013** — `progress.py` (C-Progress): `rich.progress.Progress` with three named tasks; transcribe ticks per speech segment per ADR-0010 (2 sub-pt) — maintainer
- **POD-014** — Verbosity matrix (`-v` / `-q` / `--debug` mutual exclusion) + non-TTY fallback (AC-US-3.2/3.3/3.5) (2 sub-pt) — maintainer
- **POD-015** — Event catalogue freeze: 22 tokens per ADR-0012, locked `event=done` and `event=model_download` shapes (1 sub-pt) — maintainer

### US-4 — Override defaults via config or CLI  (Should, **3 points**)
**Sprint:** SP-4
**Linked AC:** AC-US-4.1, AC-US-4.2, AC-US-4.3, AC-US-4.4
**Linked features:** F3, F4, F8
**Tasks:**
- **POD-016** — `config.py` (C-Config): `tomllib` load + `frozen=True, slots=True` `Config` dataclass per ADR-0013 + CLI merge precedence (CLI wins) + lang revalidation on config-loaded code (AC-US-4.4) (2 sub-pt) — maintainer
- **POD-017** — `backends/base.py` `select_backend()`: platform detection (`arm64-darwin` → mlx, else faster) per ADR-0003; `UsageError` exit 2 on incompatible-backend override (E7) (1 sub-pt) — maintainer

### US-5 — Be told when the tool is downloading a multi-GB model  (Must, **5 points**)
**Sprint:** SP-3 (faster-whisper) + SP-4 (mlx-whisper)
**Linked AC:** AC-US-5.1, AC-US-5.2, AC-US-5.3, AC-US-5.4
**Linked features:** F6
**Tasks:**
- **POD-018** — `backends/base.py`: `WhisperBackend` Protocol + `TranscribedSegment` NamedTuple per ADR-0003 (1 sub-pt) — maintainer
- **POD-019** — `backends/faster.py` (C-FasterWhisper): lazy import of `faster_whisper` per ADR-0011, `load(model, device)` + `transcribe(pcm, lang)`, `ImportError` / network → `ModelError` exit 5 (2 sub-pt) — maintainer
- **POD-020** — `backends/mlx.py` (C-MlxWhisper): lazy import of `mlx_whisper` per ADR-0011, mirror of POD-019 (2 sub-pt) — maintainer
- **POD-021** — First-run notice within 1 s of process start per NFR-6 / AC-US-5.1: `event=model_download model=… size_gb=…` + `huggingface_hub` download progress on stderr (1 sub-pt) — maintainer

### US-6 — Avoid clobbering a previous transcript on re-run  (Must, **2 points** — calibration anchor)
**Sprint:** SP-4
**Linked AC:** AC-US-6.1, AC-US-6.2, AC-US-6.3, AC-US-6.4
**Linked features:** F1
**Tasks:**
- **POD-022** — Output-exists validation in C-CLI: raise `OutputExistsError` (exit 6, `event=output_exists`) when resolved output exists without `--force` (AC-US-6.1, E3); also AC-US-6.4 missing-parent → `InputIOError` exit 3 (1 sub-pt) — maintainer
- **POD-023** — `--force` / `-f` opt-in path; atomic-rename invariant from POD-009 already preserves prior file on failure (AC-US-6.3) (1 sub-pt) — maintainer

### US-7 — Inspect intermediate artifacts when something looks wrong  (Should, **3 points**)
**Sprint:** SP-6
**Linked AC:** AC-US-7.1, AC-US-7.2
**Linked features:** F10
**Tasks:**
- **POD-024** — `--debug` artifact emission: `<input-stem>.debug/{decoded.wav (int16 WAV), segments.jsonl, transcribe.jsonl, commands.txt}` next to input per AC-US-7.1 (2 sub-pt) — maintainer
- **POD-025** — `--debug` dir refuse-without-`--force` per ADR-0015: same `OutputExistsError` reused, mirroring US-6 (1 sub-pt) — maintainer

### Tests & fixtures (cross-cutting)

- **POD-026** — Source `examples/sample.mp3` (LibriVox Spanish ~60 s + CC0 music bed mixed 25–35 s per SRS §14.1) + **archive raw sources to `examples/sources/` with checksums** (R-15 mitigation) + `examples/CREDITS.md` with attribution + license URLs at-time-of-bundle (2 sub-pt) — maintainer
- **POD-027** — Hand-render `examples/sample.md` (large-v3) + `tests/fixtures/sample_tiny.md` (tiny) reference outputs (1 sub-pt) — maintainer
- **POD-028** — `tests/fixtures/canción de prueba.mp3` (EC-3 path with spaces + non-ASCII) + Tier 3 integration test exercising it (1 sub-pt) — maintainer
- **POD-029** — Tier 1 unit tests (pure logic + fakes; ≤ 1 s suite; Ubuntu only — proves the boundary per ADR-0017) (5 sub-pt) — maintainer
- **POD-030** — Tier 2 contract tests (`WhisperBackend` Protocol invariants run vs `FakeBackend` AND real backends per ADR-0017) **+ a contract test asserting first-run notice fires within 1 s on a synthetic cache-miss** (R-14 mitigation) (3 sub-pt) — maintainer
- **POD-031** — Tier 3 integration tests (full CLI on `examples/sample.mp3` + tiny model on Ubuntu + macOS) (3 sub-pt) — maintainer
- **POD-032** — Property tests: NFR-3 ordering invariant on segment-merge module (100% coverage gate per NFR-8) + NFR-4 segmenter coverage (1 sub-pt) — maintainer
- **POD-033** — logfmt regex assertion in CI on all captured stderr lines per NFR-10 (1 sub-pt) — maintainer
- **POD-034** — Failure-injection integration test: kill mid-transcribe; assert no partial output file per NFR-5 / AC-US-6.3 (1 sub-pt) — maintainer
- **POD-035** — PTY / no-PTY harness for AC-US-3.1 + AC-US-3.2 (1 sub-pt) — maintainer

### Docs

- **POD-036** — `README.md` (English): install (`git clone` + `uv sync`), quickstart on `examples/sample.mp3`, output format example (SRS §1.6), model-size tradeoffs, accuracy caveats (EC-1/EC-7), exit-code table (NFR-9), logfmt event catalogue (NFR-10 + ADR-0012), 8-code lang table (SRS §1.7), observed-throughput section (SRS NFR-1 + Risk #7), **differentiator paragraph** (segment-then-transcribe + curated lang set + atomic-write contract — R-16 mitigation) (3 sub-pt) — maintainer
- **POD-037** — `docs/ARCHITECTURE.md`: 4-bullet one-pager per SRS §16.2 (pipeline + backend Protocol + noise/silence rationale + atomic-write rationale) (1 sub-pt) — maintainer
- **POD-038** — `CHANGELOG.md` (Keep-a-Changelog format) per brief §14; **per-sprint `velocity_actual=N` line at every sprint review** (Q8 + Q12 substitute) + **"regenerate examples/sample.md after large-v3 bumps" runbook entry** (R-12 mitigation) (1 sub-pt) — maintainer

### Release

- **POD-039** — `git tag v0.1.0` — first usable release (per brief §16) (1 sub-pt) — maintainer
- **POD-040** — `git tag v1.0.0` — first tagged release whose CI passes against the SRS per §16.1 + GitHub Release with auto-generated notes (1 sub-pt) — maintainer

### Spikes

- **SPK-1** — Validate combined install of TensorFlow (via `inaSpeechSegmenter`) + MLX + `faster-whisper` + `huggingface_hub` on Apple Silicon GitHub Actions runner (2 spike-points, **off-velocity**)
  - **Goal**: reduce uncertainty in SRS Risk #5 / SYSTEM_DESIGN Risk #3 — confirm the dep stack co-installs cleanly on macOS-14 arm64 runners under `uv sync` with the locked `pyproject.toml`. Failure ⇒ document a per-platform install matrix or pin around the conflict before any backend code lands.
  - **Output**: a passing CI smoke job on macOS that does `uv sync` + imports both `inaSpeechSegmenter` and `mlx_whisper` in the same process. If conflict: a written note on the resolution (extra dep group, install order, or fallback).

### Retired IDs
- **POD-012** — retired in v0.2 (never assigned in v0.1; gap preserved across the `T-N` → `POD-NNN` rename to keep IDs stable for any future reference).

## 6. Sprint backlog

Forecast velocity: **8 points/sprint** (Q2 resolved). Each sprint commits stories totaling ≤ 8 pts; cross-cutting tasks listed inline.

### SP-1 — Skeleton, CLI, decode, atomic write (theme: "stub end-to-end")
**Goal:** by end of SP-1, `podcast-script examples/sample.mp3 --lang es` decodes the audio with `ffmpeg`, runs the Pipeline orchestrator with stub segmenter + stub backend, atomically writes a stub-content Markdown next to the input, and exits 0 with the locked `event=done` summary line on stderr.
**Stories committed:** US-1 partial (POD-001, POD-002, POD-003, POD-006, POD-007, POD-009 = 1+1+1+2+3+1 = 9 sub-pts on a 8-pt US-1 → SP-1 covers ~75% of US-1; POD-008 Pipeline orchestrator deferred to SP-2).
**Cross-cutting:** POD-004 GitHub Actions baseline CI (Ubuntu only, smoke test), SPK-1 launched in parallel (off-velocity).
**Total committable points:** 8 (SP-1 budget; ramp slack absorbed by the spike running in background).
**Deliverable:** Ubuntu CI green on a smoke test that runs the CLI on `examples/sample.mp3` (sourced ahead of SP-1 if quick — else use any MP3) → asserts atomic write of a stub Markdown.
**Demo / review focus:** "the skeleton works end-to-end with stub stages; we can decode `ffmpeg` and write atomically. Tier 1 tests don't exist yet."

### SP-2 — Pipeline orchestrator + segmenter + render
**Goal:** by end of SP-2, the pipeline runs the **real** segmenter (inaSpeechSegmenter) and emits real **music start/end markers** in English with auto MM:SS / HH:MM:SS timestamps in the output Markdown. Speech text is still stub (no backend yet).
**Stories committed:** US-1 finish (POD-008 Pipeline = 3 sub-pt), US-2 (POD-010 + POD-011 = 3+2 = 5 sub-pt) → 8 sub-pt; US-2 = 5 story points.
**Cross-cutting:** none (POD-032 property tests deferred to SP-6).
**Total committable points:** 8
**Deliverable:** Ubuntu CI integration test on `examples/sample.mp3`: assert music-marker structure (`> [MM:SS — music starts]` lines present + ordered + English markers) regardless of speech text content.
**Demo / review focus:** "we can see real music regions detected; the renderer is right."

### SP-3 — faster-whisper backend + first-run UX + Tier 1 tests
**Goal:** by end of SP-3, the pipeline produces a **real Spanish transcript** via `faster-whisper` (tiny model on CPU) with the first-run download notice firing within 1 s on a cold cache.
**Stories committed:** US-5 partial (POD-018 + POD-019 + POD-021 = 1+2+1 = 4 sub-pt; POD-020 mlx-whisper deferred to SP-4).
**Cross-cutting:** POD-029 Tier 1 unit tests baseline (5 sub-pt) — but story-aligned: covers C-Decode + C-Render + C-Config + errors + segment-merge property tests.
**Total committable points:** 9 → trim POD-029 to 4 sub-pt (defer 1 sub-pt of Tier 1 to SP-6); committed = 8.
**Deliverable:** Ubuntu CI integration test: full pipeline on `examples/sample.mp3` with `--model tiny` produces a real-content Markdown matching `tests/fixtures/sample_tiny.md` (structural assertions only — `tiny` is noisy).
**Demo / review focus:** "`podcast-script examples/sample.mp3 --lang es` produces a real transcript on Linux. First-run download notice visible. Tier 1 unit suite green."

### SP-4 — mlx-whisper + config + force overwrite + macOS CI
**Goal:** by end of SP-4, the pipeline runs on **Apple Silicon via mlx-whisper**, the config-file precedence works (CLI overrides config), and `--force` / `-f` correctly gates output overwrite.
**Stories committed:** US-5 finish (POD-020 = 2 sub-pt), US-4 (POD-016 + POD-017 = 2+1 = 3 sub-pt), US-6 (POD-022 + POD-023 = 1+1 = 2 sub-pt) → US-4 (3 pts) + US-5 finish + US-6 (2 pts) = 7 sub-pt.
**Cross-cutting:** POD-030 Tier 2 contract tests baseline (1 sub-pt of 3 — establishes the FakeBackend + Protocol invariant runner; rest in SP-6).
**Total committable points:** 8
**Deliverable:** macOS CI integration test green: full pipeline on `examples/sample.mp3` via `mlx-whisper` tiny model. Config-file example committed under `examples/`. Refuse-overwrite test passes; `-f` overwrite test passes.
**Demo / review focus:** "both backends work on their respective platforms. CI matrix complete. `--force` is honored."
**Ceremony note:** **first sprint with retro added** (Q8 — SP-4 onward).

### SP-5 — Progress + verbosity + logfmt + event catalogue
**Goal:** by end of SP-5, the full UX is in place: `rich` progress bar with three phases + per-segment ticks; `-v` / `-q` / `--debug` verbosity matrix; every stderr log line is logfmt; the 22-token event catalogue is enforced.
**Stories committed:** US-3 (POD-013 + POD-014 + POD-015 = 2+2+1 = 5 sub-pt).
**Cross-cutting:** POD-003' full ADR-0008 wiring (1 sub-pt — finishing what SP-1 started minimally), POD-033 logfmt regex CI assertion (1 sub-pt), POD-035 PTY/no-PTY harness (1 sub-pt).
**Total committable points:** 8
**Deliverable:** integration test asserts logfmt regex on all captured stderr; non-TTY (piped) run produces line-per-phase fallback with no ANSI; quiet/verbose/debug each emit the right line classes (AC-US-3.5).
**Demo / review focus:** "the user sees a real progress bar in their terminal and clean logfmt logs in their pipe. The event catalogue is the contract."

### SP-6 — `--debug` artifact dir + tests Tier 1/2/3 completion + edge cases
**Goal:** by end of SP-6, `--debug` produces the four artifacts next to the input; all three test tiers run green on Ubuntu + macOS; NFR-3/NFR-4 property tests pass; failure-injection invariant passes.
**Stories committed:** US-7 (POD-024 + POD-025 = 2+1 = 3 sub-pt).
**Cross-cutting:** POD-029 Tier 1 finish (1 sub-pt), POD-030 Tier 2 finish (2 sub-pt — includes the R-14 huggingface_hub 1-s contract test), POD-032 property tests (1 sub-pt), POD-034 failure-injection (1 sub-pt).
**Total committable points:** 8
**Deliverable:** all three test tiers green on the CI matrix. Coverage report shows ≥ 80% overall + 100% on segment-merge.
**Demo / review focus:** "the test pyramid is solid; we can ship without fearing regressions."

### SP-7 — Real fixtures + integration tests + README
**Goal:** by end of SP-7, the bundled `examples/sample.mp3` is the real LibriVox + CC0 fixture (with archived sources for R-15); reference outputs are committed; the EC-3 path-with-non-ASCII fixture is exercised; the README is publishable.
**Stories committed:** none new (US-1..US-7 all done).
**Cross-cutting:** POD-026 sample.mp3 sourcing + sources/checksums (2 sub-pt), POD-027 reference outputs (1 sub-pt), POD-028 EC-3 fixture + test (1 sub-pt), POD-031 Tier 3 integration on real fixture (1 sub-pt), POD-036 README incl. R-16 differentiator paragraph (3 sub-pt).
**Total committable points:** 8
**Deliverable:** `examples/sample.mp3` is real and CI-validated; CI on Ubuntu + macOS produces a real Markdown matching `tests/fixtures/sample_tiny.md` structure. README readable on GitHub. **1–2 dogfooders invited per Q7** — bar: "did the README quickstart get them to a transcript without help?"
**Demo / review focus:** "an external user could `git clone` + `uv sync` + run the quickstart from the README and it would work."

### SP-8 — ARCHITECTURE + CHANGELOG + supply chain + v1.0.0 release
**Goal:** by end of SP-8, v1.0.0 is tagged and released. All ancillary deliverables (docs/ARCHITECTURE.md, CHANGELOG.md, Dependabot, pip-audit cron) are in place. Dependency versions frozen.
**Stories committed:** none new.
**Cross-cutting:** POD-037 ARCHITECTURE.md (1 sub-pt), POD-038 CHANGELOG.md incl. R-12 runbook entry (1 sub-pt), POD-005 Dependabot + pip-audit cron (1 sub-pt), POD-039 v0.1.0 tag (1 sub-pt — could be done at SP-7 review instead), POD-040 v1.0.0 tag + GitHub Release (1 sub-pt). **Pin `huggingface_hub`, `faster-whisper`, `mlx-whisper`, `inaSpeechSegmenter` minor versions** in `pyproject.toml` (R-14, R-17 mitigation). **Pin GitHub Actions runner image to `macos-14`** in `ci.yml` (R-13 mitigation). Buffer: 2-3 sub-pt for any spillover.
**Total committable points:** 5–7 (intentionally light — this is the "settle dust + ship" sprint).
**Deliverable:** `git tag v1.0.0` pushed; GitHub Release published; CI green against the full SRS per §16.1.
**Demo / review focus:** "v1.0.0 is live. The README quickstart works. Anyone can grab the tag."

## 7. Release roadmap

Sprint-by-sprint timeline. **Calendar dates are projections, not commitments** — they assume SP-1 starts the week of 2026-04-27 and 2-week cadence holds. Re-project at every sprint review.

| Sprint | Dates (proj.)            | Milestone                                     | Deliverable                                                         | Testable for                            |
|--------|--------------------------|-----------------------------------------------|---------------------------------------------------------------------|-----------------------------------------|
| SP-1   | 2026-04-27 – 2026-05-10  | M-1 — End-to-end stub pipeline                | CLI + decode + atomic write; stub Markdown on Ubuntu CI             | maintainer (architecture sanity)        |
| SP-2   | 2026-05-11 – 2026-05-24  | M-2 — Real music markers                      | Real segmenter + render; music-marker structure asserted            | maintainer                              |
| SP-3   | 2026-05-25 – 2026-06-07  | M-3 — Real transcript on Linux                | faster-whisper + first-run UX; real Spanish text via tiny model     | maintainer                              |
| SP-4   | 2026-06-08 – 2026-06-21  | M-4 — Cross-platform + config + force         | mlx-whisper + config.toml + `--force`; macOS CI green               | maintainer                              |
| SP-5   | 2026-06-22 – 2026-07-05  | M-5 — Full UX (progress + logfmt)             | rich Progress + verbosity matrix + logfmt + event catalogue         | maintainer                              |
| SP-6   | 2026-07-06 – 2026-07-19  | M-6 — Test pyramid + `--debug`                | All three tiers green; `--debug` artifacts; failure-injection green | maintainer                              |
| SP-7   | 2026-07-20 – 2026-08-02  | M-7 — Real fixtures + README (v0.1.0 candidate) | Real `examples/sample.mp3` + reference outputs + README publishable | maintainer + 1–2 invited dogfooders     |
| SP-8   | 2026-08-03 – 2026-08-16  | **M-8 — v1.0.0 release**                      | `git tag v1.0.0` + GitHub Release + CHANGELOG + ARCHITECTURE.md     | external users via README quickstart    |

**Release windows / external commitments:** none (no deadline).
**v0.1.0 (first usable) target:** M-7 / end of SP-7.
**v1.0.0 (format committed in writing) target:** M-8 / end of SP-8 per SRS §16.1.

## 8. User-testing cadence — resolved Q7

| Phase       | Sprint(s)        | Tester(s)                                | Format                                                                                       | Acceptance bar                                                                                          |
|-------------|------------------|------------------------------------------|----------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------|
| Self-test   | SP-1..SP-6       | maintainer only                          | run sprint deliverable on `examples/sample.mp3` (or stand-in MP3); confirm AC at sprint review | (a) AC tests green in CI matrix, (b) maintainer eyeballs the output and it looks right                  |
| Dogfooding  | SP-7 (M-7)       | maintainer + 1–2 invited podcast producers | `git clone` + `uv sync` + run quickstart from README on their own audio; report friction via GitHub Issues | (c) at least one external dogfooder has run the quickstart end-to-end without help, before the v1.0.0 tag |
| Public      | SP-8 (M-8) onward | anyone who picks up the repo             | GitHub Issues triaged at sprint planning                                                     | feedback rolls into the post-v1.0.0 backlog                                                              |

**Format**: GitHub Issues only (per brief §17). No structured sessions, no surveys, no telemetry.

## 9. Dependencies & critical path

**Cross-story dependencies (intra-project):**
- **POD-008 (Pipeline)** → blocks POD-010, POD-011, POD-013, POD-019, POD-020 (everything that's wired into the orchestrator).
- **POD-018 (WhisperBackend Protocol)** → blocks POD-019, POD-020 (both backends implement it).
- **POD-003 (logging_setup) initial** → blocks POD-015 (event catalogue) and POD-013 (Progress) which share the `Console` per ADR-0008.
- **POD-026 (real `examples/sample.mp3`)** → blocks POD-027 (reference outputs) and POD-031 (Tier 3 on real fixture). Workaround: use any stand-in MP3 in SP-1..SP-6.
- **POD-009 (atomic write)** → required by AC-US-6.3; brought into SP-1 so US-6 in SP-4 only adds the `--force` opt-in.

**Cross-team / vendor dependencies:**
- **Hugging Face Hub availability** (first-run only — POD-019, POD-020). Risk if HF is down on first run; subsequent runs offline.
- **GitHub Actions macOS runners** for SPK-1 + SP-4 onward; pinned to `macos-14` per R-13 mitigation in SP-8.
- **LibriVox + CC0 audio sourcing** (POD-026): no vendor SLA; raw sources archived to `examples/sources/` with checksums per R-15 mitigation.

**Critical path** (longest dependency chain to v1.0.0):
SP-1 (POD-001, POD-002, POD-003, POD-006, POD-007) → SP-2 (POD-008, POD-010, POD-011) → SP-3 (POD-018, POD-019, POD-021) → SP-4 (POD-020, POD-016, POD-017, POD-022, POD-023) → SP-5 (POD-013, POD-014, POD-015) → SP-6 (POD-024, POD-029 finish, POD-030 finish, POD-032, POD-034) → SP-7 (POD-026, POD-027, POD-031, POD-036) → SP-8 (POD-037, POD-038, POD-040)

**Slack capacity** in the plan: SP-8 is intentionally underbudget (~5–7 sub-pts vs. 8 forecast), absorbing 2–3 sub-pt of expected spillover from SP-1..SP-7.

## 10. Risk register

Format: `R-N (category) — title` | Likelihood × Impact = Priority | Mitigation | Owner | Re-assess. **17 entries** after Q9.

**Risk-review policy (Q11 resolved in v0.4):** all 17 risks are reviewed at every sprint planning, ~10 min total. The five **headline risks** (R-1, R-2, R-6, R-7, R-9) — the only ones with both Likelihood ≥ M and Impact ≥ M — get explicit attention every planning. The other 12 are scanned for status changes and only require action when their listed re-assess trigger fires (e.g. "on every Dependabot PR that bumps `huggingface_hub`").

### 10.1 Technical (8)
- **R-1 (Tech) — TF (via inaSpeechSegmenter) + MLX + faster-whisper combined install on Apple Silicon may conflict** *(SRS Risk #5, SYSTEM_DESIGN Risk #3, still open)* **— headline**
  - Signal: brief §18.5 + SRS §15.5 + SYSTEM_DESIGN §5.3. Three heavy ML runtimes, one Python env, locked-no-extra-deps policy.
  - Likelihood: M, Impact: H, Priority: high.
  - Mitigation (pre-emptive): **SPK-1 in SP-1** validates combined install on macOS GitHub Actions runner before any backend code lands. If it fails, document fallback (extra dep group, install order, or runtime version pin).
  - Mitigation (contingent): document a per-platform install matrix in README; pin around the conflict in `uv.lock`.
  - Owner: maintainer.
  - Re-assess: end of SP-1 (when SPK-1 returns) and on every dep upgrade.

- **R-2 (Tech) — `inaSpeechSegmenter` mislabels music-bed under speech (SRS EC-1, Risk #3)** **— headline**
  - Signal: SRS §7 EC-1, §15.3.
  - Likelihood: H, Impact: M, Priority: high.
  - Mitigation (pre-emptive): no v1 tunables (per Q10 resolved in SRS) — accept the segmenter's labels; make it visible in `--debug`'s `segments.jsonl` so users can audit.
  - Mitigation (contingent): document the limitation prominently in README accuracy caveats; expose `--min-music-duration` post-v1 if real users hit this.
  - Owner: maintainer.
  - Re-assess: when first external user reports a false-positive / false-negative.

- **R-3 (Tech) — First-run 3 GB download UX may be perceived as "tool hung" (SRS Risk #2)**
  - Signal: SRS §15.2 + AC-US-5.1 + NFR-6.
  - Likelihood: L, Impact: M, Priority: low (mitigated structurally).
  - Mitigation: NFR-6 + AC-US-5.1 require the notice within 1 s; `event=model_download` notice + `huggingface_hub` progress bar (POD-021). Already-cached path avoids it (AC-US-5.2).
  - Owner: maintainer.
  - Re-assess: after first external run on a cold cache.

- **R-4 (Tech) — EC-3 path with non-ASCII + spaces breaks `ffmpeg` subprocess on POSIX edge cases (SYSTEM_DESIGN Risk #6)**
  - Signal: SRS §7 EC-3 + SYSTEM_DESIGN §5.6.
  - Likelihood: L, Impact: M, Priority: low.
  - Mitigation (pre-emptive): `subprocess.run(["ffmpeg", "-i", str(path), …])` with a list (not a shell string) — handles this correctly on POSIX. POD-028 fixture (`canción de prueba.mp3`) + Tier 3 test exercises it.
  - Owner: maintainer.
  - Re-assess: end of SP-7 (when POD-028 runs in CI).

- **R-5 (Tech) — Fake-vs-real backend drift in tests (SYSTEM_DESIGN Risk #9)**
  - Signal: SYSTEM_DESIGN §5.9 + ADR-0017.
  - Likelihood: M, Impact: M, Priority: medium.
  - Mitigation (pre-emptive): Tier 2 contract tests (POD-030) run shared invariant suite against `FakeBackend` AND real backends. Catches divergence at CI time.
  - Mitigation (contingent): if drift surfaces post-v1.0.0, add the missed invariant to the contract suite and the AC catalogue.
  - Owner: maintainer.
  - Re-assess: end of SP-6 (when contract suite is complete).

- **R-12 (Tech) — `large-v3` model produces materially different output from `tiny` model in CI** *(added v0.3 per Q9)*
  - Signal: SRS §14.1 (two reference outputs in different model sizes) + SRS Risk #7 (no perf SLA → no quality SLA either).
  - Likelihood: M, Impact: L, Priority: low.
  - Mitigation (pre-emptive): structural-only assertions on `tiny` (POD-027/POD-031 already in plan); CHANGELOG runbook entry "regenerate `examples/sample.md` after each large-v3 model bump" (POD-038 scope).
  - Mitigation (contingent): if `tiny` tests pass but `large-v3` output diverges visibly, document as a known model-class artifact in README accuracy caveats.
  - Owner: maintainer.
  - Re-assess: when first external user reports divergence between `examples/sample.md` and their own `large-v3` run.

- **R-14 (Tech) — `huggingface_hub` API evolution breaks first-run download contract (NFR-6, AC-US-5.1)** *(added v0.3 per Q9)*
  - Signal: AC-US-5.1 1-s notice + NFR-6 + ADR-0011 lazy-import semantics + ADR-0012 event catalogue (`event=model_download` is part of the contract).
  - Likelihood: L, Impact: M, Priority: low.
  - Mitigation (pre-emptive): pin `huggingface_hub` minor in `pyproject.toml` at SP-8; **Tier 2 contract test (POD-030 expansion) asserts the 1-s notice fires on a synthetic cache-miss**.
  - Mitigation (contingent): if hub API breaks, fall back to a stderr-only notice without the progress bar (degrades gracefully without violating AC-US-5.1's 1-s requirement).
  - Owner: maintainer.
  - Re-assess: on every Dependabot PR that bumps `huggingface_hub`.

- **R-17 (Tech) — `faster-whisper` API shape changes between versions** *(added v0.3 per Q9)*
  - Signal: SRS Risk #1 (two-backend complexity) + ADR-0011 lazy-import scope + WhisperBackend Protocol abstraction (ADR-0003) which isolates the API change to a single file.
  - Likelihood: L, Impact: M, Priority: low.
  - Mitigation (pre-emptive): pin `faster-whisper` and `mlx-whisper` minors in `pyproject.toml` at SP-8; the Protocol abstraction (ADR-0003) confines any breakage to `backends/faster.py` or `backends/mlx.py`.
  - Mitigation (contingent): if a major version bump is forced (security CVE), handle in a tactical patch sprint; the Protocol prevents leakage to other modules.
  - Owner: maintainer.
  - Re-assess: on every Dependabot PR that bumps `faster-whisper` or `mlx-whisper`.

### 10.2 Operational (4)
- **R-6 (Ops) — Solo-maintainer bus factor of 1** **— headline**
  - Signal: brief §17 (solo maintainer).
  - Likelihood: M, Impact: H (project goes dormant if maintainer steps away), Priority: high.
  - Mitigation (pre-emptive): comprehensive README + ARCHITECTURE.md + 17 ADRs + tested examples — anyone forking can pick it up. CHANGELOG documents the breaking-change contract (NFR-9 exit codes + NFR-10 event catalogue).
  - Mitigation (contingent): maintainer adds a `MAINTENANCE.md` post-v1.0.0 with bus-factor handover notes if they sense reduced availability.
  - Owner: maintainer.
  - Re-assess: every quarter.

- **R-7 (Ops) — Side-project velocity variance (work + life crowding evening capacity)** **— headline**
  - Signal: brief §17 + working-assumption §1.3 in this plan.
  - Likelihood: H, Impact: M, Priority: high.
  - Mitigation (pre-emptive): yesterday's-weather forecasting; SP-8 deliberately under-budget to absorb spillover; calendar dates flagged as projections only; no external deadline commitments. **Per-sprint `velocity_actual=N` line in CHANGELOG** (Q8/Q12 substitute) keeps the variance signal visible even during the no-retro period.
  - Mitigation (contingent): if velocity drops below 5 pts/sprint for 2 consecutive sprints, drop `Should` stories US-4 + US-7 from v1.0.0 (they slip to v1.1.0).
  - Owner: maintainer.
  - Re-assess: every sprint review.

- **R-8 (Ops) — TensorFlow + MLX + faster-whisper install on a contributor's Mac**
  - Signal: SRS Risk #5 (overlaps R-1 but framed for a future contributor, not the maintainer's own CI).
  - Likelihood: M, Impact: L, Priority: low.
  - Mitigation: pinned `uv.lock`; CI validates the combined install (R-1 mitigation); README "if install fails, file an issue with `uv pip list` output" runbook.
  - Owner: maintainer.
  - Re-assess: when the first external contributor opens an install issue.

- **R-13 (Ops) — GitHub Actions macOS runner image bumps break SPK-1 / SP-4 builds mid-project** *(added v0.3 per Q9)*
  - Signal: GitHub Actions runner versioning + SP-1 SPK-1 + SP-4 macOS dependency.
  - Likelihood: M, Impact: M, Priority: medium.
  - Mitigation (pre-emptive): **pin to `macos-14` in `ci.yml`** (not `macos-latest`), folded into POD-004 + locked at SP-8; Dependabot rule (POD-005) covers runner-version PRs so deprecation notices are visible 6 months ahead.
  - Mitigation (contingent): respond to a forced image bump in a tactical patch sprint; Tier 3 integration test on `examples/sample.mp3` (POD-031) is the regression detector.
  - Owner: maintainer.
  - Re-assess: every quarter (image rev cadence) and on any CI failure pointing at runner-version drift.

### 10.3 Business (5)
- **R-9 (Biz) — Exit-code stability becomes implicit contract once published (SRS Risk #8)** **— headline**
  - Signal: SRS §15.8 + NFR-9 + §16.1.
  - Likelihood: M, Impact: H, Priority: high.
  - Mitigation (pre-emptive): exit-code table front-and-center in README + `--help`; CHANGELOG calls out any change as a SemVer-major break (per SRS §16.1).
  - Mitigation (contingent): if a code reassignment is unavoidable, ship as v2.0.0 with a deprecation cycle.
  - Owner: maintainer.
  - Re-assess: pre-v1.0.0 freeze (SP-8) and on any new error class.

- **R-10 (Biz) — logfmt event-catalogue stability becomes implicit contract for log-grepping users (SRS Risk #9)**
  - Signal: SRS §15.9 + ADR-0012 + NFR-10.
  - Likelihood: M, Impact: M, Priority: medium.
  - Mitigation (pre-emptive): 22-token catalogue frozen in ADR-0012; README documents it; CHANGELOG calls out additions (minor) vs. removals/renames (major).
  - Owner: maintainer.
  - Re-assess: pre-v1.0.0 freeze + on any new event proposal post-v1.0.0.

- **R-11 (Biz) — Curated 8-code `--lang` set surprises users who try `--lang ja` etc. (SRS Risk #10)**
  - Signal: SRS §15.10 + §1.7.
  - Likelihood: M, Impact: L, Priority: low.
  - Mitigation: error message lists the eight + did-you-mean suggestion (POD-006); README §1.7 explains rationale (test coverage); adding a code = small docs/test PR per SRS §14.1.
  - Owner: maintainer.
  - Re-assess: on every Issue requesting a new language code.

- **R-15 (Biz) — `examples/sample.mp3` LibriVox + CC0 sourcing falls through (recording vanishes / license re-interpreted)** *(added v0.3 per Q9)*
  - Signal: SRS §14.1 spec'd source but didn't cache files; SRS Risk #6 closed in SRS but reopened here as a maintenance concern.
  - Likelihood: L, Impact: M, Priority: low.
  - Mitigation (pre-emptive): **archive raw sources to `examples/sources/` with checksums** (POD-026 scope expansion); record license URLs + retrieval date in `examples/CREDITS.md` at-time-of-bundle.
  - Mitigation (contingent): if a source disappears post-v1.0.0, replace with another LibriVox/CC0 clip; POD-027/POD-031 structural-only assertions make the fixture replaceable without breaking CI.
  - Owner: maintainer.
  - Re-assess: on every link-check (could be added as a low-priority CI step) or any 404 reported on a source URL.

- **R-16 (Biz) — Competing OSS tool makes this redundant before v1.0.0** *(added v0.3 per Q9 — affects adoption, not v1.0.0 ship)*
  - Signal: brief §17 (solo OSS) + brief §11 (GitHub-only distribution); the broader `whisper.cpp` / `whisperx` / `faster-whisper` direct-CLI ecosystem.
  - Likelihood: L, Impact: M, Priority: low.
  - Mitigation (pre-emptive): **README differentiator paragraph** in POD-036 — segment-then-transcribe pipeline (avoids Whisper hallucinations on music — EC-7), curated lang set with did-you-mean, atomic-write contract, exit-code stability. These are the unique selling points relative to a thin Whisper wrapper.
  - Mitigation (contingent): if a competing tool ships a superset before v1.0.0, fold the differentiator argument into README front-matter; otherwise no project changes needed.
  - Owner: maintainer.
  - Re-assess: every quarter; specifically scan PyPI / GitHub trending for "podcast transcription" tools.

### 10.4 Closed risks
- (none yet)

## 11. Ceremony & grooming policy — resolved Q8 + Q11

Lightened for solo maintainer. Q8 selected the "even lighter" option: **planning + review only for SP-1..SP-3; retro added from SP-4 onward**. Q11 added the **"review all 17 risks at every planning"** policy.

| Ceremony | When | Time-box | Output |
|----------|------|----------|--------|
| Planning | start of every sprint | ~30 min total: ~10 min backlog re-rank + DoR + sprint goal; **~10 min risk review across all 17 entries (headline subset R-1/R-2/R-6/R-7/R-9 first)** ; ~10 min story commitment | sprint goal sentence + committed backlog + any new R-N entries promoted to headline if their L×I has shifted |
| Daily standup | — (skipped, solo) | — | — |
| Review | end of every sprint | ~20 min | run sprint deliverable on `examples/sample.mp3` (or stand-in); confirm AC for committed stories; **write the `velocity_actual=N` line + cause-if-missed sentence into CHANGELOG** (§4.3) |
| Retro | **end of SP-4 onward only** (NOT SP-1..SP-3 per Q8) | ~15 min | start/stop/continue note; folded into next planning |
| Backlog refinement | ad-hoc, mid-sprint | as needed | new `POD-NNN` task added with next free ID, routed to a future sprint |

**No-retro period (SP-1..SP-3) implication:** lighter overhead during the high-uncertainty early sprints; downside is qualitative lessons go uncaptured. The CHANGELOG `velocity_actual=N` line is the substitute — it preserves the data needed for honest yesterday's-weather refinement and surfaces variance even without a formal retro.

**Mid-sprint scope changes:** reject by default. Exception: a Must-blocking ADR question that surfaces during implementation — handle in a tactical patch sprint or absorb by descoping a Should story. Newly discovered work is added as a `POD-NNN` task with the next free ID and routed to a future sprint, not pulled into the current one without rebudgeting.

## Open questions (this round)

### Q14 — Final-pass: anything missing, off, or under-considered? (Meta)
**Why pick the recommended option:** at 92% aggregate confidence, with §6 SP-1 fully ready to start Monday and the §10 risk register covering all real signals from the inputs, no specific gap is obvious. But this is the last cheap chance to surface a gut-level "wait, we forgot X" before the file freezes at v1.0. If something feels off, write it under Other.

- [x] Nothing missing — proceed to v1.0 freeze (recommended)
- [ ] Other: _____________  (e.g. "we never decided how the maintainer will publish a release announcement", "what if ffmpeg drops f32le support in a future version", "I want a `--dry-run` mode in v1")

### Q15 — Plan lifecycle post-v1.0 freeze (Plan governance)
**Why pick the recommended option:** the per-sprint `velocity_actual=N` line in CHANGELOG (Q12 confirmed) already requires per-sprint maintenance discipline. Extending that discipline to PROJECT_PLAN.md (mark stories Done as they complete; record sprint actuals next to forecasts; re-project §7 calendar after each sprint review) keeps the plan honest at ~5 min/review. The frozen variant avoids the maintenance but the plan becomes increasingly wrong as work happens — and at that point the sprint backlog table loses its value as a reference. The hybrid is half-measures: most of the cost without the value.

- [x] Living: PROJECT_PLAN.md is updated at every sprint review — story status (Done/In-progress/Slipped/Carried-forward), sprint actuals next to forecasts, calendar re-projection in §7. Each sprint review bumps the version (recommended)
- [ ] Frozen at v1.0: plan becomes a historical artifact at freeze time; actuals tracked only in GitHub Issues + CHANGELOG (low maintenance; plan goes stale)
- [ ] Hybrid: freeze §1–§5 (foundation) but keep §6 sprint backlog + §7 roadmap + §10 risks living
- [ ] Other: _____________

## Resolved questions

### Q1 — Sprint length (Cadence) — resolved in v0.2
**Selected:** 2 weeks (kept default)
**Touches:** §1.2 locked-in constraints, §2 cadence, §4.3 velocity derivation, §6 every sprint, §7 roadmap calendar projection.

### Q2 — Velocity forecast (Capacity) — resolved in v0.2
**Selected:** 8 pts/sprint (kept default)
**Touches:** §1.2 locked-in constraints, §1.3 working assumptions, §4.3 velocity forecast, §6 sprint commitment caps, §7 8-sprint roadmap, R-7 contingent mitigation threshold.

### Q3 — SP-1 deliverable scope (Sprint composition) — resolved in v0.2
**Selected:** Thin stub: skeleton + decode + atomic write, stages stubbed (kept default)
**Touches:** §4.1 upper bound rationale, §6 SP-1 goal/stories/deliverable, §9 critical path origin, R-1 SPK-1 timing.

### Q4 — Definition of Done (DoR/DoD) — resolved in v0.2
**Selected:** Merged + CI matrix (Ubuntu+macOS) green + smoke test on examples/sample.mp3 + AC verified in tests + docs updated if user-facing (kept default)
**Touches:** §1.2 locked-in constraints, §3.2 DoD, §6 every sprint deliverable.

### Q5 — Task ID convention — resolved in v0.2
**Selected:** Other — Globally numbered with `POD-` prefix and 3-digit zero-padded suffix (e.g. `POD-001, POD-002, ...`); user moved off recommendation.
**Touches:** §1.2 locked-in constraints, §1.4 glossary, §5 every task heading + body (40 IDs renamed; **POD-012 retired** because the v0.1 → v0.2 rename preserved the original gap), §6 sprint backlog references, §9 cross-story dependencies + critical path, §10 risk-register references in R-3/R-4/R-5/R-11.

### Q6 — Confirm provisional Fibonacci story estimates (Estimates) — resolved in v0.3
**Selected:** Accept all seven as final v0.2 baseline: US-1=8, US-2=5, US-3=5, US-4=3, US-5=5, US-6=2, US-7=3 (kept default).
**Touches:** §1.2 locked-in constraints (added story-estimates row), §3.1 DoR (changed "provisional" → "final"), §4.2 calibration anchor (turned bullet list into a final table), §5 every story heading (dropped `(provisional)` markers).

### Q7 — User-testing cadence (User testing) — resolved in v0.3
**Selected:** Self-test SP-1..SP-6, dogfooders at SP-7, public after v1.0.0 (kept default).
**Touches:** §1.3 working assumptions (re-pointed at SP-7 as the dogfooding milestone), §6 SP-7 deliverable + ceremony note, §7 roadmap "Testable for" column for SP-7, §8 user-testing cadence (expanded into a phase table), §9 dependencies row removed for "early Linux/macOS testers" (SP-3/SP-4 are now self-test only).

### Q8 — Ceremony cadence (Ceremonies) — resolved in v0.3
**Selected:** Even lighter — planning + review only (skip retro for SP-1..SP-3); user moved off recommendation.
**Touches:** §1.2 locked-in constraints (added ceremonies row), §1.4 glossary (added `velocity_actual=N` definition), §2 cadence summary, §4.3 velocity refinement (added the no-retro caveat + the `velocity_actual=N` substitute), §6 SP-4 ceremony note ("first sprint with retro added"), §11 Ceremony policy (rewritten as a table; explicitly marks retro NOT held SP-1..SP-3), POD-038 scope expansion (CHANGELOG must include the per-sprint velocity line), R-7 mitigation update.

### Q9 — Risk register completeness (Risks: inclusion) — resolved in v0.3
**Selected:** All six candidates ticked — R-12, R-13, R-14, R-15, R-16, R-17 (user picked the full list including the two flagged as conditional).
**Touches:** §10 risk register grew from 11 → 17 entries (R-12/R-14/R-17 in §10.1 Tech; R-13 in §10.2 Ops; R-15/R-16 in §10.3 Biz). Touches POD-026 scope (R-15: archive sources to `examples/sources/` + checksums), POD-030 scope (R-14: 1-s-notice contract test), POD-036 scope (R-16: README differentiator paragraph), POD-038 scope (R-12: large-v3 regen runbook entry), SP-8 scope (R-13: pin `macos-14`; R-14/R-17: pin lib minors in `pyproject.toml`), §1.2 (no change), §11 (no change).

### Q10 — Pre-SP-1 readiness check (Cadence / kickoff) — resolved in v0.4
**Selected:** Just go: tooling is the maintainer's local responsibility; SP-1 uses any MP3 stand-in; SPK-1 runs in parallel (kept default).
**Touches:** §1.3 working assumptions (no change — already aligned), §6 SP-1 unchanged, §9 dependencies (the "use any stand-in MP3 in SP-1..SP-6" workaround stays as the operative slack).

### Q11 — Active vs. monitor-only risk subset (Risks) — resolved in v0.4
**Selected:** Multi-check on a multi-select question — both the 5-entry headline subset (R-1, R-2, R-6, R-7, R-9) AND "All 17 every sprint." Resolved by adopting the more inclusive scope (review all 17 every planning) with the headline 5 marked explicitly so they always come first in the agenda.
**Touches:** §1.2 locked-in constraints (added risk-review-policy row), §1.4 glossary (added "headline risk" definition), §2 cadence summary (added "Risk review at every planning…" line), §10 risk register intro (added the policy paragraph + the `— headline` tag on the 5 high-priority entries), §11 ceremony table (Planning row time-box now itemizes the ~10 min risk review).

### Q12 — Velocity-refinement substitute during the no-retro period (Process) — resolved in v0.4
**Selected:** One-line `velocity_actual=N + cause` entry in CHANGELOG per sprint review (kept default).
**Touches:** §1.2 locked-in constraints (added velocity-refinement-substitute row), §1.4 glossary (already added in v0.3, no change), §4.3 (already added in v0.3, no change), §11 Review row time-box re-confirmed, POD-038 scope (already expanded in v0.3, no change), R-7 mitigation (already updated in v0.3, no change). Q12 confirmed the v0.3 draft rather than introducing new content.

### Q13 — Stop condition: ready to declare v1.0? (Meta) — resolved in v0.4
**Selected:** One more round (round 4): tighten anything still TBD; declare v1.0 next iteration (kept default).
**Touches:** procedural — drove this v0.4 close-out round; the next "go" produces v1.0 (final freeze).

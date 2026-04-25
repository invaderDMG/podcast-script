# Project Brief — v1.0  (confidence: 91%)

## Changelog
- v1.0 (2026-04-25) — finalized; locked license (MIT), CLI invocation shape (flat `podcast-script <input>`), project name (`podcast-script`), and bundled `examples/` directory; stripped iteration scaffolding (open questions, resolved questions, "still vague")
- v0.4 (2026-04-25) — locked Mac backend (`faster-whisper` + `mlx-whisper` hybrid), language flag policy (always require `--lang`), output filename convention (same-basename `.md`), model download UX (auto + progress bar), and user-level config file
- v0.3 (2026-04-25) — locked output format (Markdown `.md`), default model (`large-v3`), device policy (auto-detect), team model (solo public repo), diarization (out for v1), CI (GitHub Actions on PR + main), README language (English); flagged Mac-acceleration architectural decision and re-asked as Q13
- v0.2 (2026-04-25) — locked in Python + faster-whisper + inaSpeechSegmenter; switched distribution from PyPI to GitHub-repo-only; absorbed Spanish primary, MP3+AAC input, podcast-producer user
- v0.1 (2026-04-25) — initial draft from one-paragraph description

## Confidence by area
- Goal & scope: 99%
- Users: 85%
- Tech stack: 95%
- Data & state: 90%
- Hosting / deployment: 95%
- Local dev: 90%
- Testing: 80%
- CI: 95%
- CD / release: 90%
- Observability: 80%
- Security & compliance: 90%
- Public docs: 95%
- Private docs: 75%
- Versioning & release cadence: 80%
- Team & collaboration: 90%
- Risks: 95%

## Brief

## 1. Summary
A command-line tool that ingests an audio file (MP3, AAC, or any other format `ffmpeg`
can decode) of a podcast episode mixing speech and music, and produces a Markdown script
of the episode. The output transcript interleaves spoken content with time-stamped
annotations indicating when music segments start and end, so the script reads as a
complete representation of what is heard in the episode. Primary target language: **Spanish**;
other Whisper-supported languages work via the explicit `--lang` flag.

## 2. Goals & non-goals
- **Goals**
  - Accept an audio file path as input via CLI; output a Markdown (`.md`) file with the full transcript at the same basename next to the input.
  - Detect non-speech music regions and annotate them with start/end timestamps inline in the transcript.
  - Run locally on a developer computer without requiring a cloud account by default.
  - Work for **Spanish-language** podcasts at minimum; multilingual via Whisper, selected per-run with `--lang`.
- **Non-goals**
  - Real-time / streaming transcription.
  - Speaker diarization (knowing *who* spoke each line) — out for v1; can be added later by swapping the segmenter.
  - Music identification (naming the song/artist) — only detecting that music is present.
  - GUI, web app, or hosted service.
  - Editing/post-processing the audio file itself.
  - Publishing to PyPI / Homebrew / Docker Hub — distribution is a public GitHub repo only.
  - Auto-detecting input language — explicit `--lang` is required (no magic).

## 3. Users & use cases
- **Primary user:** Podcast producer wanting a written record of their episodes. Solo developer maintains the tool publicly on GitHub for any other producer who finds it useful.
- **Top use cases**
  1. Producing a searchable transcript of a podcast episode for archival, accessibility, or repurposing into show notes / blog posts.
  2. Generating show-note drafts that explicitly note where music breaks occur (e.g. for sponsor or chapter markers).
  3. Quickly skimming an episode by reading the script instead of re-listening.

## 4. Constraints
- Must be runnable as a CLI on macOS (developer is on Darwin 25.1.0); Linux is supported as a free-pass since Python + ffmpeg + the chosen libs all support it natively.
- No deadline, budget, or regulatory regime.
- Offline by default; no cloud calls in the v1 hot path.

## 5. Tech stack
- **Language & runtime:** Python 3.12+.
- **Speech-to-text:** OpenAI Whisper, `large-v3` model by default.
  - **Backend abstraction:** `faster-whisper` on Linux/CUDA/CPU; `mlx-whisper` on Apple Silicon (auto-selected when running on `arm64-darwin`).
  - **Override:** `--backend {faster-whisper,mlx-whisper}` and `--model {tiny,base,small,medium,large-v3,large-v3-turbo}`.
- **Music / speech segmentation:** `inaSpeechSegmenter` (CNN-based speech/music/noise/silence segmenter).
- **Audio I/O & decoding:** `ffmpeg` (system dep) for decoding any input format to mono 16 kHz PCM; `soundfile` / `numpy` for in-process handling.
- **CLI framework:** `typer` (Click-based, type-hint-driven CLI). Flat invocation: `podcast-script <input> --lang <code> [-o <output>]` (no subcommands in v1).
- **Build & dependency management:** `uv` for env + lockfile; `hatchling` as the build backend.
- **Distribution:** public GitHub repository; users `git clone` + `uv sync`.
- **GPU / acceleration:** auto-detect (`cuda > metal/mps via mlx > cpu`); user can pin via `--device`.
- **License:** MIT.

## 6. Architecture sketch
Single-process pipeline; stateless aside from on-disk Whisper / segmenter model caches.

```
  input.{mp3,aac,m4a,wav,flac,ogg,...}
      │
      ▼
  ┌────────────────┐    ffmpeg decode → mono 16 kHz PCM (in-memory or temp file)
  │   Decoder      │
  └──────┬─────────┘
         │
         ▼
  ┌──────────────────────┐    inaSpeechSegmenter →
  │  Music/Speech        │    list of (start, end, label ∈ {speech, music, noise, silence})
  │  Segmenter           │
  └──────┬───────────────┘
         │
         ▼ (speech regions only)
  ┌──────────────────────┐    Whisper transcribe → list of (start, end, text)
  │  Speech-to-Text      │    backend: faster-whisper or mlx-whisper; --lang required
  └──────┬───────────────┘
         │
         ▼ merge speech segments with music annotations, ordered by time
  ┌──────────────────────┐
  │  Script Renderer     │
  └──────┬───────────────┘
         │
         ▼
  output.md          (same basename as input, in same directory; -o overrides)
```

The backend abstraction is a single Python interface with two implementations:
```python
class WhisperBackend(Protocol):
    def transcribe(self, pcm: np.ndarray, lang: str) -> list[Segment]: ...
```
`FasterWhisperBackend` and `MlxWhisperBackend` both implement it; selection is by
platform detection (`arm64-darwin` → mlx, else faster-whisper) with `--backend` to override.

Output line shape (Markdown):
```markdown
> [00:00 — música empieza]
> [00:14 — música termina]

`00:14`  Bienvenidos de nuevo al podcast, hoy hablamos de ...

...

> [12:30 — música empieza]
> [12:42 — música termina]

`12:42`  Y con esto cerramos el episodio de esta semana.
```

Renders cleanly on GitHub, in any Markdown viewer, and as plain text in `cat`.

## 7. Local development
- **Prereqs:** Python 3.12+, `uv`, `ffmpeg` on PATH. On Apple Silicon, `mlx` and `mlx-whisper` install cleanly via `uv`; no separate Metal toolchain needed.
- **Bootstrap:** `git clone <repo> && cd podcast-script && uv sync` (creates `.venv`, installs locked deps).
- **Run on a sample:** `uv run podcast-script examples/sample.mp3 --lang es` → emits `examples/sample.md`. `-o other.md` to override.
- **Models:** `large-v3` is downloaded automatically on first use (~3 GB). Both backends use the `huggingface_hub` cache; a stderr message announces the one-time download with a progress bar.
- **Defaults via config:** `~/.config/podcast-script/config.toml` may pre-fill any CLI flag (e.g. `model = "large-v3"`, `lang = "es"`, `device = "auto"`); CLI flags always override.
- **Containerization:** out of scope.

## 8. Automated testing
- **Unit:** `pytest`. Cover the segmentation-merge logic, timestamp formatting, output renderer, config-file loading + CLI override precedence, and CLI argument parsing with mocked transcribers/segmenters.
- **Integration:** A short (~30 s) public-domain **Spanish** sample with a known transcript and a known music segment, asserted end-to-end. Kept under 1 MB and committed to `tests/fixtures/`. CI runs this with the **`tiny`** model (not `large-v3`) to keep CI fast and avoid GPU dependence; we assert structure (timestamps + music markers present + correct ordering) rather than exact transcript text, since `tiny` is noisy.
- **Lint & type-check:** `ruff` (lint + format), `mypy --strict` on the package.
- **Coverage target:** 80% lines overall; 100% on the segmentation-merge module.

## 9. CI
- **Provider:** GitHub Actions.
- **Triggers:** every PR + push to `main`.
- **Workflow `ci.yml`:**
  - Matrix: Ubuntu + macOS, Python 3.12.
  - Steps: install `ffmpeg` (`apt-get` / `brew`), `astral-sh/setup-uv`, `uv sync`, `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`, `uv run pytest`.
  - macOS job uses the `mlx-whisper` backend in the integration test (with `tiny`); Ubuntu job uses `faster-whisper` (CPU). Both must pass.
- **Required checks before merge:** lint, format, type-check, tests on both OSes.
- **Costs:** none — public repo, unlimited GitHub Actions minutes.
- **Supply-chain:** Dependabot for GitHub deps; `pip-audit` job on a weekly cron.

## 10. CD / deployment
- **Artifact:** none — there is no published package.
- **Release mechanism:** `git tag vX.Y.Z` + GitHub Release; release notes auto-generated from PRs since the last tag (`gh release create --generate-notes`).
- **Rollback:** users `git checkout` the previous tag; nothing to un-publish.
- **Secrets:** none.

## 11. Hosting & infrastructure
- N/A for runtime — local CLI.
- **Source distribution:** public GitHub repository (single canonical install path).
- **Domains & TLS:** N/A.

## 12. Observability
- **Logs:** structured logs to stderr via Python `logging`; `--verbose` flag bumps to DEBUG, `--quiet` silences everything except errors.
- **Progress:** `rich` progress bar with three named phases (decode → segment → transcribe). The transcribe phase is the slow one — show per-segment progress so the user knows the tool isn't hung during long episodes.
- **Metrics / traces:** none.
- **Crash reports:** stderr stack trace on uncaught exception; `--debug` keeps temp files for inspection and prints the exact ffmpeg / model commands run.

## 13. Security & compliance
- **AuthN / AuthZ:** none — local CLI.
- **Data handling:** input audio never leaves the local machine in the default (offline) configuration. Cloud transcription is not a current goal; if added later it must be opt-in via an explicit `--backend` flag.
- **Regulatory regime:** none assumed; the user is responsible for the licensing of audio they transcribe.
- **Dependency / SAST scanning:** Dependabot (PR-time) + `pip-audit` (weekly cron in CI).

## 14. Public documentation
- **README.md (English):** what it is, install (`git clone` + `uv sync`), quickstart with the bundled `examples/sample.mp3`, output format example, model-size tradeoffs, accuracy caveats, hardware/acceleration notes (`mlx-whisper` on Mac, `faster-whisper` elsewhere), and a config-file example.
- **LICENSE:** MIT (standard text).
- **CHANGELOG.md:** Keep-a-Changelog format, kept in sync with git tags.
- **`examples/` directory:** `examples/sample.mp3` (~1 min, ~1 MB, public-domain Spanish audio with a music segment) + `examples/sample.md` (the rendered output) — committed to the repo as a hand-runnable demo and onboarding aid.
- **No separate docs site, no HTTP API, no API reference.**

## 15. Private documentation
- **Architecture notes:** a short `docs/ARCHITECTURE.md` capturing the segment-then-transcribe pipeline + the backend-abstraction rationale (so a future contributor knows why we picked what we picked).
- **ADRs:** none initially; revisit only if a second contributor joins.
- **Runbooks:** not needed for a CLI.
- **Onboarding:** the `Local development` section of the README.

## 16. Versioning & release
- **Scheme:** SemVer; first usable release tagged `v0.1.0`. Bump to `v1.0.0` once the format is committed-to in writing.
- **Cadence:** released as ready; no fixed cadence. Releases = annotated git tags + GitHub Releases.
- **Branching model:** trunk-based; short-lived feature branches off `main`, squash-merge directly by the maintainer.

## 17. Team & collaboration
- **Team size:** solo (1 maintainer).
- **Code review:** self-merge to `main`; no required reviewers. CI must pass before merge.
- **Issue tracker:** GitHub Issues (used as bug intake from any users that pick up the tool).
- **Communication:** N/A while solo.

## 18. Risks
1. **Two-backend complexity.** Maintaining `faster-whisper` + `mlx-whisper` behind one interface means double the surface area for bugs. *Mitigation:* keep the abstraction thin (one method: `transcribe(pcm, lang) -> [(start, end, text)]`); test both in CI on the matching OS.
2. **First-run model download is ~3 GB.** Without a clear UX, users may think the tool has hung. *Mitigation:* progress bar + clear stderr message ("downloading large-v3, ~3 GB, one-time").
3. **Music/speech boundary accuracy.** `inaSpeechSegmenter` makes mistakes around quiet music *under* speech ("music bed"); annotations may be noisy. *Mitigation:* expose tunables (min-segment, threshold) and document accuracy in the README.
4. **Whisper hallucinations on music regions.** If music isn't filtered before ASR, Whisper will invent lyrics. *Mitigation:* segment first, only transcribe speech regions (already in the architecture).
5. **`inaSpeechSegmenter` pulls TensorFlow.** Heavy dep that may conflict with `mlx`/`faster-whisper` install on some Macs. *Mitigation:* validate the combined install in CI on macOS; document fallback if conflicts surface.
6. **Public-domain Spanish audio sourcing.** Bundling `examples/sample.mp3` requires a redistributable clip. *Mitigation:* source from LibriVox (public-domain audiobooks) or a Creative Commons podcast feed; mix in a short royalty-free music bed if needed.

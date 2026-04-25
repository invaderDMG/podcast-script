# Software Requirements Specification — v1.0  (confidence: 93%)

## Changelog
- v1.0 (2026-04-25) — finalized; resolved Q16–Q20 (all defaults): test fixture spec locked to LibriVox ~60 s + CC0 music bed at 25–35 s with two reference outputs (Q16; closes risk #6); CLI short-flag aliases locked to `-o`/`-f`/`-v`/`-q` only (Q17); UC-1 stderr summary line locked to logfmt with input/output/backend/model/lang/durations (Q18); v1.0.0 release trigger locked to "first tagged release whose CI passes against this SRS" (Q19); `docs/ARCHITECTURE.md` scoped to a four-bullet one-pager (Q20). Stripped iteration-only "Open questions (this round)" section; promoted Q16–Q20 to Resolved. Added §14.1 Test fixture spec; added §16 Release & maintainer artifacts. Updated §9.1 CLI grammar to include short-flag aliases; updated UC-1 step 10 summary-line shape; closed risk #6.
- v0.4 (2026-04-25) — resolved Q11–Q15: locked `--lang` validation to a curated tested-only list `{es, en, pt, fr, de, it, ca, eu}` (Q11 — moved off recommendation), kept auto-download with stderr notice (Q12), locked stderr structured logs to logfmt key=value (Q13), dropped sidecar JSON of raw segments from v1 (Q14), and locked `--debug` to keep an `<input-stem>.debug/` directory next to the input (Q15). Added F8, F9, F10; added US-7 + AC-US-7.1/7.2; added AC-US-1.5, AC-US-3.4/3.5, AC-US-4.4; added NFR-10 (logfmt) and §1.7 supported-language set.
- v0.3 (2026-04-25) — resolved Q6–Q10: locked timestamp format auto `MM:SS`/`HH:MM:SS` (Q6), noise/silence skipped from output (Q7), differentiated exit codes 0–6 (Q8), edge case set EC-1/EC-2/EC-3/EC-4/EC-7/EC-10 (Q9 — retired EC-5/EC-6/EC-8/EC-9), no segmenter tunables (Q10 — moved off recommendation). Added AC-US-1.4, AC-US-2.4, AC-US-2.5, AC-US-5.4, AC-US-6.4. Locked NFR-9 (exit-code policy).
- v0.2 (2026-04-25) — resolved Q1–Q5: actor list A1 only (Q1), single-file scope (Q2), English music markers (Q3 — moved off recommendation), refuse-overwrite-without-`--force` (Q4), no committed perf target (Q5 — moved off recommendation). Wrote Given-When-Then ACs for US-1..US-5; fully fleshed UC-1 alternative and exception flows; added US-6 (force overwrite); revised NFR-1.
- v0.1 (2026-04-25) — initial draft seeded from `PROJECT_BRIEF.md` v1.0; drafted A1 Podcast Producer; US-1..US-5; fully-fleshed UC-1; stub UC-2.

## Confidence by area
- Purpose & scope: 98%
- Actors & roles: 95%
- Features (capability list): 97%
- User stories: 92%
- Use cases (flows): 95%
- Acceptance criteria: 92%
- Edge cases: 88%
- Data requirements: 92%
- External interfaces: 95%
- Non-functional requirements: 90%
- Security & privacy: 92%
- Compliance & regulatory: 90%
- Assumptions & dependencies: 88%
- Prioritization (MoSCoW): 95%
- Traceability & validation: 92%

## 1. Purpose & scope

### 1.1 Purpose
This document specifies the functional and non-functional requirements for **`podcast-script`**, a local command-line tool that converts a podcast audio file (MP3, AAC, or any other format `ffmpeg` can decode) into a Markdown transcript that interleaves spoken content with time-stamped annotations of music segments. The audience is the solo maintainer (for implementation and self-review), future contributors (to understand intent), and any external user evaluating whether the tool fits their workflow.

### 1.2 In scope (v1)
- Single-file CLI invocation: `podcast-script <input> --lang <code> [-o <output>] [--force]`.
- Decoding any `ffmpeg`-supported audio format to mono 16 kHz PCM.
- Music vs. speech segmentation via `inaSpeechSegmenter`.
- Speech-to-text via Whisper (`large-v3` default), with a hybrid backend: `faster-whisper` on Linux/CUDA/CPU, `mlx-whisper` on Apple Silicon (auto-selected, `--backend` to override).
- Markdown output at the same basename as the input, in the same directory, unless `-o` overrides.
- Refuse to overwrite an existing output file unless `--force` is given.
- Music annotations always emitted in English (`music starts` / `music ends`), independent of `--lang`.
- Timestamps in output Markdown auto-formatted: `MM:SS` for episodes < 1 hour, `HH:MM:SS` for episodes ≥ 1 hour. Format consistent within one transcript.
- `noise` and `silence` segments produced by the segmenter are NOT emitted in the output Markdown.
- `--lang` validated against a curated tested-only set: `es, en, pt, fr, de, it, ca, eu` (8 codes). Unknown codes are rejected with exit 2 and a "did you mean?" suggestion.
- Stderr structured logs in logfmt-style key=value.
- `--debug` keeps an `<input-stem>.debug/` directory next to the input containing the decoded PCM, segmenter raw output, transcribe raw output, and a `commands.txt` recording the executed `ffmpeg` invocation.
- User-level config file at `~/.config/podcast-script/config.toml` whose values pre-fill any CLI flag; CLI flags always override.
- Auto model download with progress bar on first use (no confirmation prompt).
- `rich` progress bar covering decode → segment → transcribe phases, with `--verbose` / `--quiet` / `--debug` switches.
- Differentiated exit codes (0 ok, 1 generic, 2 usage, 3 input I/O, 4 decode, 5 model/network, 6 output-exists-without-`--force`).
- CLI short-flag aliases for the highest-traffic options: `-o` / `-f` / `-v` / `-q`.
- Bundled `examples/sample.mp3` test fixture (~60 s, ≤ 1 MB, public-domain Spanish + CC0 music bed) with two reference outputs.

### 1.3 Out of scope (v1)
- Real-time / streaming transcription.
- Speaker diarization (who said what).
- Music identification (naming songs/artists).
- Auto-detection of input language (explicit `--lang` is mandatory).
- GUI, web app, hosted service.
- Audio editing or post-processing.
- Distribution via PyPI, Homebrew, Docker Hub (GitHub repo only).
- Cloud transcription backends.
- Batch / glob / directory input (single-file only in v1; users may wrap with shell loops).
- Localized music annotation markers (English only in v1).
- Committed wall-clock performance target (observed throughput documented in README; no v1 SLA).
- Segmenter tunables exposed as flags (`--min-music-duration` etc.).
- Annotated output for `noise` and `silence` regions.
- Spec'd behaviour for: 100% music with no speech, empty/0-byte/silent input, model download interruptions, `--backend` override on incompatible platform — these scenarios fall out of decoder behaviour, the `huggingface_hub` library, or UC-1 E7 respectively, and are not separately enumerated as edge cases (IDs EC-5, EC-6, EC-8, EC-9 retired).
- Whisper-supported languages outside the v1 curated 8-code set.
- Sidecar JSON output of raw segments.
- Confirmation prompt before first-run model download.
- JSON-shaped log output (logs are logfmt key=value only).
- Environment-variable overrides for CLI flags.
- Short-flag aliases beyond `-o`/`-f`/`-v`/`-q` (no `-l`, `-m`, etc. in v1).
- ADR-style "rejected alternatives" section in `docs/ARCHITECTURE.md` (the doc is a four-bullet one-pager).

### 1.4 References
- Project brief: `PROJECT_BRIEF.md` v1.0 (2026-04-25).
- Whisper paper / model card (OpenAI).
- `faster-whisper`, `mlx-whisper`, `inaSpeechSegmenter` upstream documentation.
- Brandon Rhodes' "logfmt" convention (Heroku-style key=value log format).
- LibriVox (https://librivox.org) — public-domain audiobook source for the Spanish fixture clip.

### 1.5 Glossary
- **PCM**: pulse-code modulation; raw uncompressed audio samples.
- **Backend**: a Whisper implementation (`faster-whisper` or `mlx-whisper`) chosen at runtime.
- **Segment**: a `(start, end, label)` triple where `label ∈ {speech, music, noise, silence}` from `inaSpeechSegmenter`, or a `(start, end, text)` triple from Whisper.
- **Music bed**: quiet music playing under speech; ambiguous boundary case.
- **Annotation**: a Markdown line marking the start or end of a non-speech (music) segment, written in English (`music starts` / `music ends`). `noise` and `silence` segments are not annotated in the output.
- **Resolved output path**: the path the tool will write to, computed as `-o <path>` if given, otherwise `<input-dir>/<input-stem>.md`.
- **Timestamp format**: per-file `MM:SS` if the input duration is < 1 h, else `HH:MM:SS`. Consistent within one transcript.
- **Supported language code**: any of the v1 curated set `{es, en, pt, fr, de, it, ca, eu}`.
- **logfmt**: a flat key=value log line format (e.g. `level=info phase=decode duration_ms=1234`); values containing spaces or `=` are double-quoted.

### 1.6 Output format

The Markdown output is structured as a sequence of music annotation blocks (blockquotes) interleaved with speech lines. Music annotations are emitted in English regardless of `--lang`. `noise` and `silence` segments are never rendered.

For an episode shorter than 1 hour (`MM:SS`):

```markdown
> [00:00 — music starts]
> [00:14 — music ends]

`00:14`  Bienvenidos de nuevo al podcast, hoy hablamos de ...

...

> [12:30 — music starts]
> [12:42 — music ends]

`12:42`  Y con esto cerramos el episodio de esta semana.
```

For an episode of 1 hour or longer (`HH:MM:SS`):

```markdown
> [00:00:00 — music starts]
> [00:00:14 — music ends]

`00:00:14`  Bienvenidos de nuevo al podcast, hoy hablamos de ...

...

> [01:42:30 — music starts]
> [01:42:42 — music ends]

`01:42:42`  Y con esto cerramos el episodio de esta semana.
```

The format choice is made once per file based on total input duration; the renderer never mixes the two within one transcript.

### 1.7 Supported language codes

Exactly these eight codes are accepted by `--lang` in v1:

| Code | Language | Notes |
|------|----------|-------|
| `es` | Spanish  | Primary target; integration fixture is Spanish |
| `en` | English  | Smoke-tested in CI |
| `pt` | Portuguese | Smoke-tested |
| `fr` | French   | Smoke-tested |
| `de` | German   | Smoke-tested |
| `it` | Italian  | Smoke-tested |
| `ca` | Catalan  | Smoke-tested |
| `eu` | Basque   | Smoke-tested |

Any other code (including codes Whisper itself supports, such as `ja`, `zh`, `ru`) is rejected at parse time with exit code 2 and a "did you mean?" suggestion. To add a code post-v1, a contributor must add a smoke-test fixture and update this table — adding a code is a docs/test change, not a behavioural change in the CLI.

## 2. Overview

### 2.1 Product perspective
Standalone CLI installed by `git clone` + `uv sync`. No backend services, no shared infrastructure, no integrations beyond local `ffmpeg` and the `huggingface_hub` model cache. The tool is one process per invocation; state lives entirely on the user's local disk (input audio, output Markdown, model cache, optional `<input-stem>.debug/` directory).

### 2.2 Assumptions & dependencies
- **Assumption:** Users run on macOS (primarily Apple Silicon) or Linux. Windows is not supported in v1.
- **Assumption:** Users have ~3 GB of free disk for the `large-v3` model on first run; smaller models require less.
- **Assumption:** Users know which language their podcast is in (no auto-detect).
- **Assumption:** Users want one of the eight v1 supported languages; non-supported codes will be rejected.
- **Dependency:** `ffmpeg` installed and available on `PATH`.
- **Dependency:** `uv` for environment + dependency management.
- **Dependency:** Python 3.12+.
- **Dependency:** Internet access for first-run model download (subsequent runs are offline).
- **Dependency:** Hugging Face Hub for model artifacts.

## 3. Actors & roles

- **A1 — Podcast Producer** (primary, sole actor in v1)
  - Description: An individual producer of a podcast episode (Spanish-language by default), running the tool interactively on their personal laptop.
  - Goals: Generate an accurate, time-stamped Markdown transcript with music annotations for archival, accessibility, repurposing, or skim-reading.
  - Permissions: Full access to their own filesystem; no role separation inside the tool.
  - Notes: scripted/CI runners are explicitly not modeled as a separate actor in v1.

## 4. Features (capability list)

- **F1 — Single-file transcription with safe-by-default output** (Must)
  - Read an audio file path; produce a Markdown transcript at the resolved output path.
  - Refuse to overwrite an existing output file unless `--force` is given.
  - Stories: US-1, US-6
  - Use cases: UC-1
- **F2 — Music segment annotation (English markers, auto timestamp format, no tunables)** (Must)
  - Detect music regions and write English start/end markers (`music starts` / `music ends`) inline in the transcript.
  - Skip `noise` and `silence` regions in the output.
  - Use `MM:SS` timestamps for episodes < 1 h and `HH:MM:SS` for ≥ 1 h, consistent within one transcript.
  - No CLI tunables for the segmenter in v1; accuracy caveats documented in README.
  - Stories: US-2
  - Use cases: UC-1
- **F3 — Backend & model selection** (Must)
  - Auto-select backend by platform; allow override via `--backend`, `--model`, `--device`.
  - Stories: US-4
  - Use cases: UC-1
- **F4 — Config file defaults** (Should)
  - Read `~/.config/podcast-script/config.toml`; every key corresponds to a CLI flag; CLI overrides config.
  - Stories: US-4
  - Use cases: UC-1
- **F5 — Progress and logging UX (with `-v`/`-q` short aliases)** (Must)
  - `rich` progress bar with decode/segment/transcribe phases; `--verbose` (`-v`) / `--quiet` (`-q`) / `--debug` switches.
  - Stories: US-3, US-7
  - Use cases: UC-1
- **F6 — First-run model download** (Must)
  - Auto-download the requested model with a progress bar and a clear stderr notice; cache via `huggingface_hub`. No confirmation prompt.
  - Stories: US-5
  - Use cases: UC-2
- **F7 — Differentiated exit-code policy** (Must)
  - Distinct exit codes per documented failure class; documented in `--help` and README.
  - Stories: spans US-1, US-5, US-6
  - Use cases: UC-1, UC-2
- **F8 — Curated `--lang` set with typo suggestions** (Must)
  - Validate `--lang` at parse time against the eight v1 codes (§1.7); reject unknowns with exit 2 and a "did you mean?" suggestion using a closest-match heuristic (Levenshtein ≤ 2).
  - Stories: US-1, US-4
  - Use cases: UC-1 E2
- **F9 — logfmt structured stderr logs** (Must)
  - Every stderr log line emitted by the tool's `logging` integration uses logfmt key=value form, regardless of verbosity; the `rich` progress bar coexists on a separate stderr channel and is not subject to logfmt.
  - Stories: US-3
  - Use cases: UC-1
- **F10 — `--debug` artifact directory** (Should)
  - With `--debug`, the tool retains a sibling directory `<input-stem>.debug/` containing decoded PCM, segmenter raw output (JSONL), transcribe raw output (JSONL), and a `commands.txt` recording the executed `ffmpeg` invocation.
  - Stories: US-7
  - Use cases: UC-1

## 5. User stories

### US-1 — Transcribe a single Spanish episode to Markdown
**As a** Podcast Producer, **I want** to run the CLI on a single MP3/AAC episode in Spanish, **so that** I get a Markdown transcript next to the original file with no extra steps.
**Priority:** Must
**Linked feature:** F1, F8
**Acceptance criteria:**
- AC-US-1.1 — **Given** a valid Spanish-language MP3 at `episode.mp3` and no pre-existing `episode.md`, **When** I run `podcast-script episode.mp3 --lang es`, **Then** the tool writes `episode.md` next to the input and exits with code 0.
- AC-US-1.2 — **Given** the same input and `-o other/path.md`, **When** I run `podcast-script episode.mp3 --lang es -o other/path.md`, **Then** the output is written exactly to `other/path.md` and not to `episode.md`.
- AC-US-1.3 — **Given** an unsupported audio file (e.g. `.txt` rename or corrupt header that `ffmpeg` cannot decode), **When** I run the tool on it, **Then** the tool exits with code 4 (decode error), emits a stderr message naming the decode failure, and writes no output file.
- AC-US-1.4 — **Given** a missing or unreadable input path, **When** I run the tool, **Then** the tool exits with code 3 (input I/O error), emits a stderr message naming the path and reason, and writes no output file.
- AC-US-1.5 — **Given** an unknown `--lang` code (e.g. `--lang ess`, `--lang ja`), **When** I run the tool, **Then** the tool exits with code 2 before any decode work, emits a stderr message listing the eight supported codes, and — if the unknown code is within Levenshtein distance 2 of a supported code — also includes a "did you mean `<closest>`?" suggestion.

### US-2 — See music segments annotated with timestamps
**As a** Podcast Producer, **I want** music regions called out inline in the transcript with their start and end timestamps in English, **so that** I can locate sponsor breaks, intros, and outros without re-listening.
**Priority:** Must
**Linked feature:** F2
**Acceptance criteria:**
- AC-US-2.1 — **Given** an episode containing at least one music region of ≥ 2 seconds clearly bounded by speech, **When** the tool transcribes it, **Then** the output Markdown contains a `> [<ts> — music starts]` line and a `> [<ts> — music ends]` line at the start and end of that region, in time order, before/after the surrounding speech lines.
- AC-US-2.2 — **Given** the music annotation language requirement, **When** the tool runs with any supported `--lang`, **Then** the music marker text is always English (`music starts` / `music ends`).
- AC-US-2.3 — **Given** the ordering invariant (NFR-3), **When** the output is rendered, **Then** every emitted line's leading timestamp is ≥ the previous emitted line's leading timestamp.
- AC-US-2.4 — **Given** an input < 1 hour duration, **When** the tool emits the transcript, **Then** every timestamp uses `MM:SS` format and no `HH:` prefix appears. **Given** an input ≥ 1 hour duration, **Then** every timestamp uses `HH:MM:SS` format and no two-digit-only `MM:SS` form appears in that file.
- AC-US-2.5 — **Given** the segmenter labels regions as `noise` or `silence`, **When** the tool emits the transcript, **Then** no annotation line is emitted for those regions; the transcript only contains speech lines and `music starts`/`music ends` annotations.

### US-3 — Get progress feedback during long episodes
**As a** Podcast Producer, **I want** a progress bar that shows decode → segment → transcribe phases and per-segment progress within transcribe, **so that** I can see the tool is working during a long episode and roughly estimate completion.
**Priority:** Must
**Linked feature:** F5, F9
**Acceptance criteria:**
- AC-US-3.1 — **Given** a TTY stderr, **When** the tool runs with default verbosity, **Then** a progress bar appears showing three named phases (decode, segment, transcribe) and updates per segment during transcribe.
- AC-US-3.2 — **Given** a non-TTY stderr (e.g. piped to a file), **When** the tool runs, **Then** the progress bar degrades to a one-line-per-phase plain-text update and does not emit ANSI control sequences.
- AC-US-3.3 — **Given** `--quiet` (`-q`), **When** the tool runs successfully, **Then** no progress bar or informational stderr lines are emitted; only error lines (if any) appear.
- AC-US-3.4 — **Given** any verbosity that emits log lines, **When** the tool emits a log line, **Then** that line is logfmt key=value, must contain at minimum `level=<info|warn|error|debug>` and `event=<short-token>`, and any value containing whitespace or `=` is double-quoted.
- AC-US-3.5 — **Given** the verbosity matrix, **Then**: `--quiet`/`-q` ⇒ only `level=error` lines; default ⇒ `level=info` and above + progress bar; `--verbose`/`-v` ⇒ `level=debug` and above + progress bar; `--debug` ⇒ same as `--verbose` plus the artifact directory of US-7.

### US-4 — Override defaults via config or CLI
**As a** Podcast Producer, **I want** to pre-fill common flags (model, language, device) in a user config file and override per-run via CLI flags, **so that** I don't repeat the same arguments every time but can still tune for a specific episode.
**Priority:** Should
**Linked feature:** F3, F4, F8
**Acceptance criteria:**
- AC-US-4.1 — **Given** a `~/.config/podcast-script/config.toml` containing `lang = "es"` and `model = "large-v3"`, **When** I run `podcast-script episode.mp3` with no `--lang` flag, **Then** the tool uses `lang=es` from the config and proceeds without error.
- AC-US-4.2 — **Given** the same config, **When** I run `podcast-script episode.mp3 --lang en --model tiny`, **Then** CLI flags win: the run uses `lang=en` and `model=tiny`.
- AC-US-4.3 — **Given** no config file exists and no `--lang` flag is provided, **When** the tool starts, **Then** the tool exits with code 2 (usage error) and a stderr message stating that `--lang` is required and listing the eight supported codes.
- AC-US-4.4 — **Given** a config file that sets `lang` to an unsupported code (e.g. `lang = "ja"`), **When** the tool starts with no `--lang` CLI flag, **Then** the same validation as AC-US-1.5 fires and the tool exits with code 2.

### US-5 — Be told when the tool is downloading a multi-GB model
**As a** Podcast Producer running the tool for the first time, **I want** a clear stderr notice and a progress bar when the `large-v3` model is being downloaded, **so that** I don't think the tool has hung on a 3 GB silent download.
**Priority:** Must
**Linked feature:** F6
**Acceptance criteria:**
- AC-US-5.1 — **Given** the `large-v3` model is not present in the `huggingface_hub` cache, **When** the tool starts the transcribe phase, **Then** within 1 second a stderr message identifying the model name and approximate size (e.g. "downloading large-v3, ~3 GB, one-time") is emitted, followed by a download progress bar.
- AC-US-5.2 — **Given** the model is already cached, **When** the tool runs, **Then** no download notice is emitted.
- AC-US-5.3 — **Given** an aborted download (Ctrl-C), **When** the user re-runs the tool, **Then** the tool resumes or restarts the download cleanly and does not leave a half-loaded model in use.
- AC-US-5.4 — **Given** the network is unreachable on first run, **When** the tool tries to load a missing model, **Then** the tool exits with code 5 (model/network error) and a stderr message naming the model and the failure mode.

### US-6 — Avoid clobbering a previous transcript on re-run
**As a** Podcast Producer iterating on flags, **I want** the tool to refuse to overwrite an existing output file by default and accept a `--force` (`-f`) flag to opt in, **so that** I don't silently destroy a manually-edited transcript.
**Priority:** Must
**Linked feature:** F1
**Acceptance criteria:**
- AC-US-6.1 — **Given** `episode.md` already exists at the resolved output path, **When** I run `podcast-script episode.mp3 --lang es` (no `--force`), **Then** the tool exits with code 6, emits a stderr message naming the existing file and instructing the user to pass `--force`/`-f`, and `episode.md` is left unchanged.
- AC-US-6.2 — **Given** the same precondition, **When** I run with `--force` (or `-f`), **Then** the existing `episode.md` is replaced with the freshly generated transcript and the tool exits 0.
- AC-US-6.3 — **Given** any failure during transcription after a `--force` run has begun, **When** the failure occurs, **Then** the previous `episode.md` is preserved (write atomically: write to a temp file in the same directory, rename on success).
- AC-US-6.4 — **Given** the resolved output path's parent directory does not exist, **When** I run the tool (with or without `--force`), **Then** the tool exits with code 3, emits a stderr message naming the missing parent, and creates no directories.

### US-7 — Inspect intermediate artifacts when something looks wrong
**As a** Podcast Producer (or a maintainer reproducing a bug), **I want** `--debug` to keep all intermediate artifacts of a run on disk in a predictable location, **so that** I can inspect what the segmenter and transcriber actually produced and share a self-contained reproduction.
**Priority:** Should
**Linked feature:** F10
**Acceptance criteria:**
- AC-US-7.1 — **Given** `--debug` is passed, **When** a run completes (success or failure), **Then** an `<input-stem>.debug/` directory exists next to the input and contains: `decoded.wav` (mono 16 kHz PCM), `segments.jsonl` (one JSON object per segment with `{start, end, label}`), `transcribe.jsonl` (one JSON object per speech segment with `{start, end, text}`), and `commands.txt` (the exact `ffmpeg` command line used).
- AC-US-7.2 — **Given** `--debug` is NOT passed, **When** a run completes, **Then** no `<input-stem>.debug/` directory is created and any temp files used during the run are deleted before the process exits.

## 6. Use cases

### UC-1 — Transcribe a single audio file
**Primary actor:** A1 Podcast Producer
**Secondary actors:** none
**Preconditions:**
- `podcast-script` is installed (`uv sync` succeeded) and `ffmpeg` is on `PATH`.
- The input file exists and is readable by the user.
- The chosen Whisper model is either already cached locally **or** the machine has internet access to download it (see UC-2).
- The user provides a supported `--lang` code (or has one set in config).
**Postconditions (success):**
- A Markdown file is written at the resolved output path.
- Process exits with code 0 and a final stderr line summarizing duration, output path, and selected backend/model in logfmt form.
**Postconditions (failure):**
- No partial Markdown file is left at the output path; any pre-existing file at that path is unmodified.
- Process exits with the appropriate non-zero code (see exception flows) and a human-readable error on stderr.

**Main flow (happy path):**
1. User runs `podcast-script episode.mp3 --lang es` (optionally with `-o`, `-f`, `-v`, `-q`).
2. CLI parses arguments and merges with `~/.config/podcast-script/config.toml`; CLI flags win on conflict.
3. CLI validates: `--lang` is set and is one of `{es, en, pt, fr, de, it, ca, eu}`; input exists and is readable; `ffmpeg` is on `PATH`; the resolved output path either does not exist or `--force` is set; the parent directory of the resolved output path exists.
4. CLI selects backend by platform: `arm64-darwin` → `mlx-whisper`, otherwise `faster-whisper` (unless `--backend` overrides).
5. Decoder phase: `ffmpeg` decodes `episode.mp3` to mono 16 kHz PCM (in-memory or — under `--debug` — written to `<input-stem>.debug/decoded.wav`). Total duration is captured to choose the timestamp format (`MM:SS` if < 1 h, else `HH:MM:SS`). Progress bar shows decode phase.
6. Segmenter phase: `inaSpeechSegmenter` produces `(start, end, label)` segments. Under `--debug`, segments are written to `<input-stem>.debug/segments.jsonl`. Progress bar shows segment phase.
7. Transcribe phase: speech regions only are passed to the chosen Whisper backend with `--lang`. If the model is missing locally, UC-2 is invoked transparently. Under `--debug`, raw transcribe output is written to `<input-stem>.debug/transcribe.jsonl`. Progress bar shows per-segment progress.
8. Renderer merges speech segments with English `music starts` / `music ends` annotations in time order; `noise` and `silence` segments are dropped from output. All timestamps use the format chosen at step 5.
9. CLI writes the Markdown to a temp file in the same directory as the resolved output path, then atomically renames it to the resolved output path.
10. CLI prints the locked logfmt summary line on stderr — `level=info event=done input=<path> output=<path> backend=<name> model=<name> lang=<code> duration_in_s=<n> duration_wall_s=<n>` — and exits with code 0.

**Alternative flows:**
- **A1 — Backend / model / device override** (at step 4): if `--backend`, `--model`, or `--device` is provided, the override takes precedence over auto-detection. The chosen backend MUST be compatible with the platform (see E7).
- **A2 — Custom output path with `-o`** (at step 3): if `-o <path>` is provided, the resolved output path is `<path>` instead of the default same-basename location. Existence and writability of `<path>`'s parent directory are validated; a missing parent is an exception (E6).
- **A3 — `--force`/`-f` overwrite** (at step 3): if the resolved output path exists and `--force` is set, the run proceeds; the old file is only replaced when the atomic rename in step 9 succeeds. If the run fails before step 9, the old file is preserved.
- **A4 — `--debug` artifact retention** (steps 5/6/7/end): the run additionally retains `<input-stem>.debug/` next to the input (US-7); without `--debug`, all intermediate files are deleted before exit.

**Exception flows (each has a designated exit code per NFR-9):**
- **E1 — Input file not found / not readable** (at step 3): exit code **3**, stderr `error: input file not found: <path>` (or `not readable`). No output is written.
- **E2 — `--lang` missing or unsupported** (at step 3): exit code **2**. If neither CLI nor config supplies `--lang`: stderr `error: --lang is required (e.g. --lang es). Supported: es, en, pt, fr, de, it, ca, eu`. If `--lang <code>` is not in the curated set: stderr lists the eight accepted codes and, when within Levenshtein distance 2 of one of them, a `did you mean <closest>?` suggestion (AC-US-1.5).
- **E3 — Output file exists without `--force`** (at step 3): exit code **6**, stderr `error: <path> already exists; pass --force (-f) to overwrite`. Existing file is unmodified.
- **E4 — `ffmpeg` not on `PATH`** (at step 3 or step 5): exit code **2**, stderr `error: ffmpeg not found on PATH; see README install steps`. No output.
- **E5 — Decode failure inside `ffmpeg`** (at step 5): exit code **4**, stderr names the `ffmpeg` exit status and a one-line summary. No output.
- **E6 — Output parent directory does not exist** (at step 3): exit code **3**, stderr `error: parent directory of <path> does not exist`. No directories are auto-created. No output.
- **E7 — Backend incompatible with platform** (at step 4 / A1): exit code **2**, stderr explaining the constraint (e.g. "mlx-whisper requires Apple Silicon").
- **E8 — Model load / download failure** (at step 7, via UC-2): exit code **5**, stderr names the model and underlying cause. No output.
- **E9 — Unexpected internal error** (any step): exit code **1**, full traceback printed under `--debug`, otherwise a one-line summary. No output.

**Linked stories:** US-1, US-2, US-3, US-4, US-6, US-7
**Related edge cases:** EC-1, EC-2, EC-3, EC-4, EC-7, EC-10

### UC-2 — First-run model download
**Primary actor:** A1 Podcast Producer
**Secondary actors:** Hugging Face Hub (external dependency)
**Preconditions:**
- The selected Whisper model is **not** present in the `huggingface_hub` cache.
- The machine has internet access reachable to Hugging Face Hub.
**Postconditions (success):**
- The model is cached locally; UC-1 transcribe phase resumes without further downloads.
**Postconditions (failure):**
- Partial download is cleaned up by `huggingface_hub`; the run exits with code 5 (UC-1 E8).

**Main flow:**
1. UC-1 reaches the transcribe phase and asks the backend to load the requested model.
2. Backend detects the model is missing locally.
3. CLI prints to stderr: `downloading <model>, ~<size>, one-time` (also a logfmt log line `level=info event=model_download model=<name> size_gb=<n>`) and renders a download progress bar. **No confirmation prompt is shown.**
4. `huggingface_hub` downloads the model to its cache directory.
5. Once complete, UC-1 resumes from step 7 of its main flow.

**Alternative flows:**
- **A1 — Resume after partial download**: if `huggingface_hub` detects a resumable partial download, it resumes; the user-facing notice in step 3 still fires.

**Exception flows:**
- **E1 — Network unreachable**: exit code **5** (UC-1 E8), stderr names the model and "network unavailable".
- **E2 — Disk full / write permission denied on cache directory**: exit code **5**, stderr names the cache path and reason.
- **E3 — Checksum / integrity failure on download**: rely on `huggingface_hub` retry/error semantics; surface a clear error and exit code **5**.

**Linked stories:** US-5
**Related edge cases:** none in v1.

## 7. Edge cases

The v1 committed edge case set is six entries. IDs **EC-5, EC-6, EC-8, EC-9 are retired** — those scenarios are addressed by other parts of the spec (decoder/library/exception flows) without dedicated edge-case handling.

- **EC-1 — Music bed under speech** ({F2, UC-1}) — `inaSpeechSegmenter` may flag a region as music when speech is also present, or speech when music is also present, causing missing or extra `music starts/ends` markers. v1 behaviour: trust the segmenter's labels. **Mitigation:** documented as a known accuracy caveat in the README (no CLI tunables in v1).
- **EC-2 — Output file already exists** ({F1, UC-1, US-6}) — covered by E3 (default refuse, exit code 6) and A3 (`--force`/`-f`).
- **EC-3 — Input path with spaces or non-ASCII characters** ({UC-1}) — MUST work end-to-end. The integration test fixture in `tests/fixtures/` includes a path with both.
- **EC-4 — Very long episode (≥ 3 hours)** ({F5, NFR-2}) — progress bar must remain responsive; memory must not grow as a function of episode length (segment-by-segment streaming). Output uses `HH:MM:SS` (AC-US-2.4).
- **EC-7 — Whisper hallucinations on borderline music regions** ({F2, F3}) — mitigated structurally by transcribing speech regions only. Documented in README; no programmatic detection in v1.
- **EC-10 — Input format that `ffmpeg` cannot decode** ({F1, UC-1}) — covered by AC-US-1.3 and UC-1 E5 (exit code 4).

## 8. Data requirements

- **Inputs**
  - Audio file: any format `ffmpeg` can decode. No size cap enforced by the tool itself.
  - User config file (optional): `~/.config/podcast-script/config.toml`.
- **Outputs**
  - Markdown file: UTF-8, default extension `.md`, default path = same basename next to input. Atomically written: temp file in the same directory, then renamed on success (AC-US-6.3).
  - Optional `<input-stem>.debug/` directory (only when `--debug` is given) containing:
    - `decoded.wav` — mono 16 kHz PCM of the decoded input.
    - `segments.jsonl` — one JSON object per segmenter-emitted region (`{"start": …, "end": …, "label": …}`).
    - `transcribe.jsonl` — one JSON object per speech segment passed to Whisper (`{"start": …, "end": …, "text": …}`).
    - `commands.txt` — the literal `ffmpeg` command line invoked.
- **In-process state**
  - Decoded mono 16 kHz PCM (in-memory or under `<input-stem>.debug/decoded.wav` when `--debug`).
  - Segmenter output: list of `(start, end, label)`.
  - Transcribe output: list of `(start, end, text)`.
  - Total duration captured during decode for timestamp-format selection (AC-US-2.4).
- **On-disk caches**
  - `huggingface_hub` model cache (Whisper models, ~3 GB for `large-v3`).
  - `inaSpeechSegmenter` model cache (smaller).
- **Lifecycle / retention**
  - Tool writes a single Markdown output per run; never deletes prior outputs except via `--force` overwrite (US-6).
  - Caches are managed by their owning libraries; the tool does not GC them.
  - Without `--debug`, any in-process temp files are deleted before exit (AC-US-7.2). With `--debug`, the artifact directory is retained until the user removes it.
  - No PII is stored or transmitted by the tool itself in the default offline configuration.
- **Sensitive-data classification**
  - Audio content may contain PII, copyrighted material, or sensitive speech. The tool processes it locally and does not transmit it. Responsibility for licensing of transcribed audio rests with the user. Note: `<input-stem>.debug/decoded.wav` and `transcribe.jsonl` contain a verbatim copy of the audio and the Whisper transcription respectively; users sharing a `--debug` directory must treat it with the same care as the original audio.

## 9. External interfaces

### 9.1 User interfaces

**Primary channel:** terminal CLI (`typer`-based). Full grammar:

```
podcast-script <input>
  --lang <code>          (one of: es, en, pt, fr, de, it, ca, eu)
  [-o, --output <path>]
  [-f, --force]
  [--model <tiny|base|small|medium|large-v3|large-v3-turbo>]
  [--backend <faster-whisper|mlx-whisper>]
  [--device <auto|cpu|cuda|mps>]
  [-v, --verbose | -q, --quiet | --debug]
```

Short-flag aliases are limited to the four highest-traffic options: `-o`, `-f`, `-v`, `-q`. `--lang`, `--model`, `--backend`, `--device`, and `--debug` are long-form only.

- **Localization / i18n:** transcribes any of the eight v1 supported languages via `--lang`; UI strings (errors, log messages, README) are in English; music annotation markers in the transcript are always English regardless of `--lang`.
- **Accessibility:** stderr output respects `NO_COLOR`; progress bar degrades gracefully for non-TTY stderr (AC-US-3.2).
- **`--help`:** lists every flag, the eight supported `--lang` codes, and the documented exit-code table (NFR-9).
- **Logs:** all log lines on stderr are logfmt key=value (NFR-10). The `rich` progress bar uses ANSI control sequences on a TTY and degrades on non-TTY (US-3).

### 9.2 APIs consumed
- **Hugging Face Hub** — Whisper / segmenter model downloads. Failure mode if unavailable: first-run only — clear error with retry guidance (UC-2 E1, AC-US-5.4). Subsequent runs are offline.

### 9.3 APIs exposed
- **Public Python interface (informal):** the project may expose a `WhisperBackend` Protocol (`transcribe(pcm, lang) -> [Segment]`) but does not commit to a stable Python API in v1. Users interact via the CLI.

### 9.4 Hardware / files / other
- Reads any file path on the local filesystem; writes one file per run (and optionally one debug directory).
- Uses CPU, optionally GPU (CUDA on Linux, Metal/MPS via MLX on Apple Silicon).
- Requires `ffmpeg` on `PATH`.

## 10. Non-functional requirements

- **NFR-1 — Performance (no v1 SLA):** v1 does NOT commit to a wall-clock target. Observed throughput on the maintainer's reference Apple Silicon machine for `large-v3` Spanish and on CPU `faster-whisper` `tiny` SHALL be measured and documented in the README.
- **NFR-2 — Memory footprint:** peak RSS MUST not be a function of episode length; the transcribe phase processes speech regions one at a time (covers EC-4).
- **NFR-3 — Correctness — annotation ordering:** music annotations and speech segments MUST be emitted in strictly non-decreasing time order in the output Markdown.
- **NFR-4 — Correctness — segmenter coverage and output filtering:** every second of the input MUST be accounted for by at least one segment label in the segmenter pass (no internal gaps). The Markdown renderer MUST emit lines only for `speech` and `music` segments; `noise` and `silence` MUST NOT produce annotation lines (AC-US-2.5).
- **NFR-5 — Reliability — atomic output:** the tool MUST exit with code 0 only when a complete, well-formed Markdown file has been written to the resolved output path; if any phase fails, no partial file may exist at the resolved output path (atomic write via temp + rename — AC-US-6.3).
- **NFR-6 — Usability — first-run UX:** the user MUST be told within 1 second of process start that a multi-GB download is in progress, if applicable (AC-US-5.1).
- **NFR-7 — Portability:** the tool MUST run on macOS 14+ (Apple Silicon) and Ubuntu LTS without code changes.
- **NFR-8 — Maintainability:** lint (`ruff`), format (`ruff format`), and type-check (`mypy --strict`) MUST pass on every PR; coverage ≥ 80% lines overall, 100% on the segmentation-merge module.
- **NFR-9 — Exit-code policy:** the tool MUST use the following exit codes, documented in `--help` and README:
  - `0` — success
  - `1` — generic / unexpected internal error (UC-1 E9)
  - `2` — usage error: bad flags, missing/unsupported `--lang`, `ffmpeg` not on PATH, incompatible backend (UC-1 E2, E4, E7)
  - `3` — input I/O error: input not found or unreadable, output parent dir missing (UC-1 E1, E6, AC-US-6.4)
  - `4` — decode error: `ffmpeg` failed to decode the input (UC-1 E5)
  - `5` — model / network error (UC-1 E8, UC-2 E1/E2/E3, AC-US-5.4)
  - `6` — output file exists without `--force` (UC-1 E3, AC-US-6.1)
- **NFR-10 — Log format:** every stderr log line emitted by the tool's `logging` integration MUST be logfmt key=value, MUST include at minimum `level` and `event`, and any value containing whitespace or `=` MUST be double-quoted. The `rich` progress bar is exempt from this requirement (it is a UI element, not a log stream).

## 11. Security & privacy
- **AuthN/AuthZ:** none (local CLI, no users).
- **PII handling:** input audio may contain PII; the tool processes locally and does not transmit it in the default configuration. Cloud transcription is out of scope; if added later it MUST be opt-in via an explicit `--backend` flag. Note: `--debug` writes a verbatim copy of the audio (`decoded.wav`) and the transcription (`transcribe.jsonl`) to disk next to the input; this is not a data exfiltration path but increases on-disk footprint of sensitive content.
- **Encryption at rest / in transit:** N/A (local file IO only).
- **Audit logging:** stderr logs include input path, chosen backend/model/device, durations, and event names — all in logfmt. No remote telemetry.
- **Threats considered:**
  - **T1 — Path injection / arbitrary write:** the `-o` flag MUST resolve to a path the user has write permission for; the tool MUST NOT auto-create directories outside the explicitly given path's parent (E6 enforces this). The `<input-stem>.debug/` directory is created next to the input and follows the same rule.
  - **T2 — Dependency supply chain:** mitigated by Dependabot + `pip-audit` weekly cron in CI.
  - **T3 — Model integrity:** rely on `huggingface_hub` checksum verification; surface errors clearly (UC-2 E3).

## 12. Compliance & regulatory
- **Applicable regimes:** none assumed. The user is responsible for the licensing/consent status of audio they transcribe.
- **Specific obligations triggered:** none.
- **Evidence / artefacts:** none required.

## 13. Prioritization (MoSCoW for v1)
- **Must:** F1, F2, F3, F5, F6, F7, F8, F9; US-1, US-2, US-3, US-5, US-6; NFR-3, NFR-4, NFR-5, NFR-6, NFR-7, NFR-8, NFR-9, NFR-10.
- **Should:** F4, F10; US-4, US-7.
- **Could:** *(empty in v1 — segmenter tunables, sidecar JSON, env-var overrides, additional short-flag aliases all explicitly deferred)*.
- **Won't (this release):** speaker diarization, music identification, batch/glob/directory input, GUI, cloud backends, PyPI/Homebrew/Docker distribution, auto language detection, localized music annotation markers, committed perf SLA, segmenter tunables (`--min-music-duration` etc.), annotated `noise`/`silence` regions, dedicated handling for 100%-music inputs, dedicated handling for empty/0-byte inputs, dedicated handling for interrupted model downloads, dedicated handling for `--backend` on incompatible platform, Whisper languages outside the curated 8-code set, sidecar JSON of raw segments, JSON-shaped logs, environment-variable overrides for CLI flags, confirmation prompt before model download, short-flag aliases for `--lang`/`--model`/`--backend`/`--device`/`--debug`, ADR-style "rejected alternatives" appendix in `docs/ARCHITECTURE.md`.

## 14. Traceability & validation

| Requirement | Acceptance criteria | Verification method |
|-------------|---------------------|---------------------|
| US-1        | AC-US-1.1, AC-US-1.2, AC-US-1.3, AC-US-1.4, AC-US-1.5 | Integration test on `examples/sample.mp3` with `tiny` model in CI; exit-code assertions per AC; lang-typo test |
| US-2        | AC-US-2.1, AC-US-2.2, AC-US-2.3, AC-US-2.4, AC-US-2.5 | Same fixture + a synthetic ≥ 1 h fixture for the HH:MM:SS branch |
| US-3        | AC-US-3.1, AC-US-3.2, AC-US-3.3, AC-US-3.4, AC-US-3.5 | PTY/no-PTY harness; logfmt regex assertion; verbosity matrix unit tests |
| US-4        | AC-US-4.1, AC-US-4.2, AC-US-4.3, AC-US-4.4 | Unit test on config-merge precedence and unsupported-code rejection |
| US-5        | AC-US-5.1, AC-US-5.2, AC-US-5.3, AC-US-5.4 | Mocked `huggingface_hub` cache + first-run notice and network-failure assertion |
| US-6        | AC-US-6.1, AC-US-6.2, AC-US-6.3, AC-US-6.4 | Unit + integration: pre-create file, run with/without `--force`, atomic-rename + missing-parent assertions |
| US-7        | AC-US-7.1, AC-US-7.2 | Integration: run with `--debug`, assert directory contents; run without, assert no debug dir and no leftover temp files |
| NFR-3       | n/a (invariant)     | Property test on the segment-merge module |
| NFR-4       | AC-US-2.5           | Property test on the segmenter pass + integration assertion |
| NFR-5       | AC-US-6.3           | Failure-injection integration test (kill mid-transcribe; assert no output file) |
| NFR-6       | AC-US-5.1           | Same as US-5 |
| NFR-9       | All exit-code ACs   | Per-AC integration tests asserting exit codes |
| NFR-10      | AC-US-3.4           | logfmt regex applied to all captured stderr log lines in CI |
| NFR-1       | n/a (no v1 SLA)     | README benchmark notes; not in CI |

### 14.1 Test fixture spec

The `examples/` and `tests/fixtures/` directories ship the following committed assets:

- **`examples/sample.mp3`** — ~60 s, ≤ 1 MB. Source: a public-domain LibriVox Spanish audiobook clip (read aloud, mono speech). A CC0 music bed (~5–10 s) is mixed in at approximately 25–35 s, bookended by speech on either side, so the fixture exercises the music-detection path without ambiguous boundaries. Exact source attribution and license URLs are recorded in `examples/CREDITS.md`.
- **`examples/sample.md`** — the rendered output from running `podcast-script examples/sample.mp3 --lang es --model large-v3` on the maintainer's reference Apple Silicon machine. Hand-reviewed for accuracy. Serves as the "what does a real transcript look like" demo.
- **`tests/fixtures/sample_tiny.md`** — the rendered output from running the same command with `--model tiny`. Used by CI; assertions are structural (timestamps present, music markers in correct order, English markers, `MM:SS` format because the fixture is < 1 h, no `noise`/`silence` lines) rather than exact-text, since `tiny` is noisy.
- A **path with spaces and non-ASCII characters** is also included in `tests/fixtures/` for EC-3 coverage, e.g. `tests/fixtures/canción de prueba.mp3` (a copy of the same fixture renamed).

Adding a smoke-test fixture for any of the other seven curated languages (en/pt/fr/de/it/ca/eu) follows the same pattern and is the unit of work required to add a new code to §1.7.

## 15. Risks & open issues

1. **Two-backend complexity** — `faster-whisper` + `mlx-whisper` doubles surface area. Mitigation: thin Protocol abstraction, both tested in CI on matching OS.
2. **First-run 3 GB download UX** — see US-5 / NFR-6 / AC-US-5.1 / AC-US-5.4.
3. **Music-bed boundary accuracy** — `inaSpeechSegmenter` errs on quiet music under speech. Mitigation: README documents the limitation; no CLI tunables in v1. If real users hit this, expose `--min-music-duration` post-v1.
4. **Whisper hallucinations** — mitigated by segment-then-transcribe (EC-7).
5. **TensorFlow conflict from `inaSpeechSegmenter`** — validate combined install on macOS in CI.
6. **Public-domain Spanish sample sourcing for `examples/`** — closed in v1.0: spec'd in §14.1 (LibriVox clip + CC0 music bed). Acquisition tracked in a follow-up project issue; the SRS itself no longer treats this as open.
7. **No committed perf target** — risk of an unnoticed perf regression. Mitigation: README "observed throughput" section updated on each release.
8. **Exit-code stability (NFR-9)** — once published in `--help` and README, the integer values become an implicit contract for shell scripts wrapping the tool. Document any changes prominently in CHANGELOG and consider it a breaking change.
9. **logfmt log-line stability (NFR-10)** — the set of `event=<token>` names emitted at default verbosity becomes an implicit contract for users grepping logs. Document the catalogue in README and treat additions as minor, removals/renames as breaking.
10. **Curated `--lang` set** — rejecting Whisper-supported codes outside the eight may surprise users who try `--lang ja`. Mitigation: error message lists the supported set and the README explains the rationale (test coverage). Adding a code post-v1 is a small, documented change (see §14.1).

## 16. Release & maintainer artifacts

### 16.1 v1.0.0 release trigger
v1.0.0 is the first tagged release whose CI passes against this SRS — i.e., every Must-priority requirement and acceptance criterion verified in §14 passes on both the Ubuntu and macOS CI jobs. No additional gating (external user feedback, beta period, etc.) is required. The artifacts that constitute the "format committed in writing" are:

- §1.6 — Output format (Markdown shape, English markers, timestamp format).
- §1.7 — Supported language codes (the eight-code set).
- §10 NFR-9 — Exit-code policy.
- §10 NFR-10 — Log format.
- §9.1 — CLI grammar (flag set + short aliases).

Changes to any of these after v1.0.0 are breaking and warrant a major-version bump per SemVer.

### 16.2 Maintainer-facing documents

- **`docs/ARCHITECTURE.md`** — a one-page note covering exactly four topics:
  1. The segment-then-transcribe pipeline and why it exists (avoids Whisper hallucinations on music).
  2. The `WhisperBackend` Protocol and the platform-detection rule (`arm64-darwin` → `mlx-whisper`, else `faster-whisper`).
  3. The noise/silence renderer-filter rationale (segmenter must cover them; renderer must not emit them).
  4. The atomic-write rationale (write-temp-then-rename preserves prior `episode.md` on failure).
  No ADR-style "rejected alternatives" section in v1 (deferred).
- **README.md** — covers install, quickstart on `examples/sample.mp3`, output format example, model-size tradeoffs, accuracy caveats (EC-1, EC-7), hardware notes, exit-code table (NFR-9), logfmt event catalogue (NFR-10), and the supported-language table (§1.7).
- **CHANGELOG.md** — Keep-a-Changelog format, kept in sync with git tags; breaking changes to §1.6 / §1.7 / NFR-9 / NFR-10 / §9.1 are called out at the top of the entry.

## Resolved questions

### Q1 — Actor list for v1 (Actors) — resolved in v0.2
**Selected:** A1 Podcast Producer only (kept default).
**Touches:** §3 Actors, §6 UC-1/UC-2 (single actor), §13 MoSCoW.

### Q2 — Input scope for v1 (Scope) — resolved in v0.2
**Selected:** Single file only (kept default).
**Touches:** §1.2 In scope, §1.3 Out of scope, §6 UC-1.

### Q3 — Music annotation language inside the transcript (Features) — resolved in v0.2
**Selected:** Always English (`music starts` / `music ends`) — moved off recommendation.
**Touches:** §1.2 In scope, §1.5 Glossary, §1.6 Output format, §4 F2, §5 US-2 + AC-US-2.2, §9.1 i18n note.

### Q4 — Behaviour when output path already exists (Features / Edge cases) — resolved in v0.2
**Selected:** Refuse to overwrite by default; require `--force` to replace (kept default).
**Touches:** §1.2 In scope, §4 F1, §5 US-6 + AC-US-6.1/6.2/6.3/6.4, §6 UC-1 step 3 + A3 + E3, §8 Data requirements, §10 NFR-5, §13 MoSCoW.

### Q5 — Performance NFR baseline (Non-functional requirements) — resolved in v0.2
**Selected:** No specific target; document observed throughput in README — moved off recommendation.
**Touches:** §1.3 Out of scope, §10 NFR-1, §13 MoSCoW, §14 Traceability, §15 Risks.

### Q6 — Timestamp format in the output Markdown (Output format / F2) — resolved in v0.3
**Selected:** Auto: `MM:SS` if total duration < 1 h, `HH:MM:SS` if ≥ 1 h, consistent within one transcript (kept default).
**Touches:** §1.2 In scope, §1.5 Glossary, §1.6 Output format, §4 F2, §5 AC-US-2.4, §6 UC-1 steps 5/8, §8 Data requirements.

### Q7 — Behaviour for `noise` and `silence` segments from the segmenter (F2) — resolved in v0.3
**Selected:** Skip both — no markers for noise or silence regions (kept default).
**Touches:** §1.2 In scope, §1.5 Glossary, §1.6 Output format, §4 F2, §5 AC-US-2.5, §6 UC-1 step 8, §10 NFR-4.

### Q8 — Exit-code policy (NFR-9) — resolved in v0.3
**Selected:** Differentiated codes 0–6 (kept default).
**Touches:** §1.2 In scope, §4 F7, §5 multiple ACs, §6 UC-1 E1–E9 + UC-2 E1–E3, §9.1, §10 NFR-9, §13 MoSCoW, §14 Traceability, §15 Risks #8.

### Q9 — Edge cases to commit to in v1 (Edge cases) — resolved in v0.3
**Selected:** EC-1, EC-3, EC-4, EC-7, EC-10 (and EC-2 retained). Dropped: EC-5, EC-6, EC-8, EC-9 — IDs retired.
**Touches:** §1.3 Out of scope, §6 UC-1, §7 Edge cases, §13 MoSCoW Won't.

### Q10 — Segmenter tunables exposed as CLI flags (F2 / Risk #3) — resolved in v0.3
**Selected:** Expose nothing in v1; document accuracy caveat only — moved off recommendation.
**Touches:** §1.3 Out of scope, §4 F2, §13 MoSCoW Could (now empty in part because of this), §15 Risks #3.

### Q11 — `--lang` validation policy (CLI / E2) — resolved in v0.4
**Selected:** Validate against curated tested-only list `{es, en, pt, fr, de, it, ca, eu}`; reject others — moved off recommendation.
**Touches:** §1.2 In scope, §1.3 Out of scope, §1.5 Glossary, §1.7 Supported language codes, §4 F8, §5 AC-US-1.5 + AC-US-4.4, §6 UC-1 step 3 + E2, §13 MoSCoW, §14 Traceability, §15 Risks #10.

### Q12 — First-run model-download UX (UC-2 / US-5) — resolved in v0.4
**Selected:** No prompt; auto-download with stderr notice (kept default).
**Touches:** §1.2 In scope, §1.3 Out of scope, §4 F6, §6 UC-2 step 3.

### Q13 — Structured-log shape on stderr (F5 / observability) — resolved in v0.4
**Selected:** logfmt key=value (kept default).
**Touches:** §1.2 In scope, §1.3 Out of scope, §1.4 References, §1.5 Glossary, §4 F9, §5 AC-US-3.4, §10 NFR-10, §11 audit logging, §14 Traceability, §15 Risks #9.

### Q14 — Sidecar JSON of raw segments (Could-bucket / F2) — resolved in v0.4
**Selected:** Drop from v1 (kept default).
**Touches:** §1.3 Out of scope, §13 MoSCoW.

### Q15 — `--debug` artifact behaviour (F5 / observability) — resolved in v0.4
**Selected:** `<input-stem>.debug/` next to the input (kept default).
**Touches:** §1.2 In scope, §4 F10, §5 US-7 + AC-US-7.1/7.2 + AC-US-3.5, §6 UC-1 steps 5/6/7 + A4, §8 Data requirements, §11 PII handling note, §13 MoSCoW.

### Q16 — `examples/sample.mp3` fixture spec (Test fixtures / Risk #6) — resolved in v1.0
**Selected:** LibriVox ~60 s + CC0 music bed at 25–35 s; commit `examples/sample.md` (large-v3) and `tests/fixtures/sample_tiny.md` (tiny) reference outputs (kept default).
**Touches:** §1.2 In scope (test fixture clause), §1.4 References (LibriVox), §14.1 Test fixture spec (new subsection), §15 Risks #6 (closed).

### Q17 — CLI short-flag aliases (CLI grammar / F5) — resolved in v1.0
**Selected:** Alias `-o`, `-f`, `-v`, `-q` only; long-form for the rest (kept default).
**Touches:** §1.2 In scope (short-flag clause), §1.3 Out of scope (other aliases explicitly Won't), §4 F5 (short alias clause), §5 AC-US-3.3 + AC-US-6.1/6.2 (mention `-q`/`-f`), §6 UC-1 step 1 + E3, §9.1 CLI grammar block.

### Q18 — Stderr summary line shape (UC-1 step 10 / F9) — resolved in v1.0
**Selected:** logfmt summary `level=info event=done input=… output=… backend=… model=… lang=… duration_in_s=… duration_wall_s=…` (kept default).
**Touches:** §6 UC-1 step 10 (locked summary line), §15 Risks #9 (this line is part of the implicit logfmt contract).

### Q19 — When does v0.x become v1.0.0? (Versioning) — resolved in v1.0
**Selected:** v1.0.0 is the first tagged release whose CI passes against this SRS (kept default).
**Touches:** §16.1 Release trigger (new subsection); enumerates the five "format committed in writing" artifacts.

### Q20 — Maintainer-facing artifact `docs/ARCHITECTURE.md` (Private docs) — resolved in v1.0
**Selected:** One-page note covering the four bullets — pipeline, backend protocol, noise/silence rationale, atomic-write rationale (kept default).
**Touches:** §1.3 Out of scope (ADR appendix explicitly Won't), §16.2 Maintainer-facing documents (new subsection).

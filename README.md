# podcast-script

Transcribe a podcast episode to Markdown — speech text plus English-language
markers around music regions — from a single CLI invocation.

```sh
podcast-script episode.mp3 --lang es
# → episode.md, with > [MM:SS — music starts] / [MM:SS — music ends] markers
```

## Why this and not a thinner Whisper wrapper

Three deliberate choices set this tool apart from a `whisper.cpp` /
`whisperx` / `faster-whisper`-CLI front-end:

- **Segment-then-transcribe.** Audio is first split into speech / music /
  noise / silence regions by `inaSpeechSegmenter`, then Whisper is invoked
  *only* on the speech regions. The result: no Whisper hallucinations on
  music intros (EC-7) and explicit start/end markers around every music
  bed.
- **Curated `--lang` set with did-you-mean.** Only the eight smoke-tested
  codes `{es, en, pt, fr, de, it, ca, eu}` are accepted; anything else
  (`ja`, `zh`, `ru`, …) exits 2 with a Levenshtein-≤-2 suggestion. Adding
  a code is a docs+test PR, not a behavioural change — quality stays
  bounded.
- **Atomic-write contract.** The output Markdown is written to a
  same-directory temp file and `os.replace`'d to the target path. A run
  that fails mid-transcribe leaves any prior output byte-for-byte intact
  (AC-US-6.3). The same principle gates the `--debug` artifact directory
  (`OutputExistsError` exit 6 unless `--force`).

## Install

You need Python 3.12+, [`uv`](https://docs.astral.sh/uv/) and `ffmpeg` on
PATH:

```sh
# uv (one-time)
curl -LsSf https://astral.sh/uv/install.sh | sh

# ffmpeg
brew install ffmpeg          # macOS
sudo apt install ffmpeg      # Debian / Ubuntu
```

Then clone and install:

```sh
git clone https://github.com/invaderDMG/podcast-script.git
cd podcast-script
uv sync           # installs locked deps into .venv
```

The first run downloads the chosen Whisper model (~75 MB for `tiny`,
~3 GB for `large-v3`) into the standard `huggingface_hub` cache. A
notice fires within 1 second of process start so you don't think the
tool has hung (AC-US-5.1).

## Quickstart

A real, license-clean fixture ships in `examples/sample.mp3` (~60 s
LibriVox Spanish speech with a CC0 Chopin music bed at 25–35 s). Try
the `tiny` model first to confirm everything wires together:

```sh
uv run podcast-script examples/sample.mp3 \
    --lang es --model tiny --backend faster-whisper \
    -o /tmp/sample.md
```

You'll see the locked logfmt event stream on stderr (`event=startup`
→ `event=done`) and a [rich](https://rich.readthedocs.io) progress bar
on a TTY — degraded to plain logfmt on a pipe (AC-US-3.2). The output
Markdown lands at `/tmp/sample.md`; expect it to look like:

```markdown
`00:01`  Las fabulaste es opo,

`00:03`  grabado para librevox.org por Christina Chu.

> [00:25 — music starts]
> [00:35 — music ends]

`00:35`   a su amiga. Pero el águila, expresiando la insignificancia ...
```

`tiny` is noisy by design. Use `--model large-v3` (Apple Silicon)
or `--model medium` (CPU / CUDA) for production-quality output.

## Output format

A single file per run, Markdown, English music markers regardless of
`--lang`. `noise` and `silence` segments are dropped entirely
(AC-US-2.5).

For an episode shorter than 1 hour, timestamps use `MM:SS`:

```markdown
> [00:00 — music starts]
> [00:14 — music ends]

`00:14`  Bienvenidos de nuevo al podcast, hoy hablamos de ...

…

> [12:30 — music starts]
> [12:42 — music ends]

`12:42`  Y con esto cerramos el episodio de esta semana.
```

For an episode of 1 hour or longer, all timestamps use `HH:MM:SS`:

```markdown
> [00:00:00 — music starts]
> [00:00:14 — music ends]

`00:00:14`  Bienvenidos de nuevo al podcast, hoy hablamos de ...

…

> [01:42:30 — music starts]
> [01:42:42 — music ends]

`01:42:42`  Y con esto cerramos el episodio de esta semana.
```

The format choice is made once per file based on total input duration
(AC-US-2.4); the renderer never mixes the two within one transcript.

## CLI reference

```text
podcast-script <INPUT>
    --lang <es|en|pt|fr|de|it|ca|eu>
    [-o, --output <path>]
    [-f, --force]
    [--model <tiny|base|small|medium|large-v3|large-v3-turbo>]
    [--backend <auto|faster-whisper|mlx-whisper>]
    [--device <auto|cpu|cuda|mps>]
    [-v, --verbose | -q, --quiet | --debug]
```

`--lang` is the only required flag. The three verbosity flags are
mutually exclusive (passing two raises a usage error). Short aliases
`-o`, `-f`, `-v`, `-q` are part of the v1 contract; everything else
is long-form only.

### Exit codes (NFR-9)

The integer values are the published shell-script contract:

| Code | Meaning | Example trigger |
|------|---------|-----------------|
| `0` | success | normal completion |
| `1` | generic / unexpected internal error | bug; surfaces with `--debug` traceback |
| `2` | usage error | bad flags, missing `--lang`, `ffmpeg` not on `PATH`, mutually-exclusive verbosity flags, `mlx-whisper` off Apple Silicon |
| `3` | input I/O error | input file not found / unreadable, output parent missing |
| `4` | decode error | `ffmpeg` returned non-zero |
| `5` | model / network error | first-run HF Hub download failure, model file corrupt |
| `6` | output exists without `--force` | output Markdown OR `--debug` artifact dir already on disk |

Any change to these values is a SemVer-major break — they're treated as
part of the format contract per SRS §16.1.

## Config file

Pre-fill any flag in `~/.config/podcast-script/config.toml` so you don't
type it every run. CLI flags always win on conflict.

```toml
# ~/.config/podcast-script/config.toml
lang = "es"
model = "large-v3"
backend = "auto"   # arm64-darwin → mlx-whisper, else faster-whisper
device = "auto"
```

Then:

```sh
podcast-script episode.mp3        # → uses lang=es, model=large-v3 from config
podcast-script episode.mp3 --lang en --model tiny  # → CLI wins
```

A config-loaded `lang` is validated identically to a CLI `--lang` —
`lang = "ja"` exits 2 with the same did-you-mean message (AC-US-4.4).
The `--force` and verbosity flags are CLI-only by design (a TOML
default of `force = true` would be a footgun against the
refuse-overwrite gate).

## Inspect intermediate artifacts (`--debug`)

Pass `--debug` to keep every intermediate step on disk for inspection:

```sh
podcast-script episode.mp3 --lang es --debug
# →  episode.debug/decoded.wav        (mono 16 kHz int16 WAV)
#    episode.debug/segments.jsonl     ({"start", "end", "label"} per segment)
#    episode.debug/transcribe.jsonl   ({"start", "end", "text"} per speech segment)
#    episode.debug/commands.txt       (the exact ffmpeg argv used)
```

The `transcribe.jsonl` is flushed line-by-line as transcripts are
produced, so a mid-loop failure (backend OOM, GPU drop, etc.) leaves a
partial file you can inspect — AC-US-7.1's "success or failure" clause.

A pre-existing `<input-stem>.debug/` directory is treated like a
pre-existing output Markdown: refused with exit 6 unless you also pass
`--force`, in which case it's `rmtree`'d and recreated. Mirror of
US-6's "never silently destroys prior work" rule (ADR-0015).

Without `--debug`, no artifacts land and no temp files survive the run
(AC-US-7.2).

## Supported languages (SRS §1.7)

Only these eight codes are accepted in v1:

| Code | Language | Notes |
|------|----------|-------|
| `es` | Spanish | Primary target; integration fixture is Spanish |
| `en` | English | Smoke-tested in CI |
| `pt` | Portuguese | Smoke-tested |
| `fr` | French | Smoke-tested |
| `de` | German | Smoke-tested |
| `it` | Italian | Smoke-tested |
| `ca` | Catalan | Smoke-tested |
| `eu` | Basque | Smoke-tested |

Any other code (including codes Whisper itself supports — `ja`, `zh`,
`ru` …) is rejected at parse time with exit 2 and a "did you mean ?"
suggestion when the typo is within Levenshtein distance 2 of a
supported code (AC-US-1.5). To add a code post-v1 a contributor must
add a smoke-test fixture and update this table — adding a code is a
docs/test change, not a behavioural change in the CLI.

## Model-size tradeoffs

Whisper model sizes are ordered by accuracy and download size; pick
the smallest one that's good enough for your audio:

| Model | ~Disk | Use when |
|-------|-------|----------|
| `tiny` | 75 MB | Smoke tests, CI, "is this thing on?" runs |
| `base` | 140 MB | Quick demos, low-latency on CPU |
| `small` | 460 MB | Hands-free dictation, clean studio audio |
| `medium` | 1.5 GB | Most podcasts on CPU `faster-whisper` |
| `large-v3` | 3 GB | Production quality on Apple Silicon `mlx-whisper` |
| `large-v3-turbo` | 1.6 GB | `large-v3` quality at smaller footprint |

The first run downloads the chosen model into `huggingface_hub`'s
cache (`~/.cache/huggingface/`) and re-uses it forever after. You can
delete the cache to free disk; the next run will re-download.

## Accuracy caveats

- **Quiet music under speech may go undetected** (EC-1 / R-2).
  `inaSpeechSegmenter` operates on energy + spectral features and
  errs toward labelling "speech with quiet musical background" as
  pure speech, omitting the music marker. v1 has no tunables for
  this; if your podcast frequently has speech-over-music transitions,
  expect occasional missed markers. Inspect `episode.debug/segments
  .jsonl` to see the labels the segmenter actually produced.
- **Whisper hallucinations on music** (EC-7) are mitigated
  *structurally* by transcribing speech regions only — Whisper never
  sees the music bed, so it can't invent fake captions for it. The
  cost is being slightly conservative about speech boundaries; long
  monologues are kept intact, but a 200 ms transition between speech
  and music can land on either side of the cut depending on the
  segmenter's energy threshold.
- **`tiny` and `base` produce noisy text** — they exist for smoke
  testing, not production. Reach for `medium` or larger before
  publishing the transcript.

## Logfmt event catalogue (NFR-10 / ADR-0012)

Every stderr line emitted by the tool is logfmt — `key=value` pairs
separated by spaces, with whitespace-containing values double-quoted.
The 22-token `event=…` set is **frozen at v1.0**; treat it as the
implicit grep contract for shell wrappers.

| Group | Tokens |
|-------|--------|
| Lifecycle (4) | `startup`, `config_loaded`, `backend_selected`, `done` |
| Model lifecycle (3) | `model_load_start`, `model_load_done`, `model_download` |
| Phase boundaries (8) | `decode_start`, `decode_done`, `segment_start`, `segment_done`, `transcribe_start`, `transcribe_done`, `render_done`, `write_done` |
| Terminal errors (6) | `usage_error`, `input_io_error`, `decode_error`, `model_error`, `output_exists`, `internal_error` |

`event=done` is the locked summary line per SRS UC-1 step 10. Its key
order is preserved by the formatter:

```
level=info event=done input=<path> output=<path> backend=<name> model=<name> lang=<code> duration_in_s=<n> duration_wall_s=<n>
```

`event=model_download` (UC-2 step 3) carries `model=…` and a `size_gb=…`
hint so you can decide whether to step away from the keyboard for a
moment. A future addition to the catalogue is a SemVer-minor change;
removing or renaming an existing token is a SemVer-major break (per
SRS §16.1).

The full ADR is at
[`docs/adr/0012-event-catalogue-freeze.md`](docs/adr/0012-event-catalogue-freeze.md).

## Verbosity matrix (AC-US-3.5)

| Flag | Logger level | Progress bar | Notes |
|------|--------------|--------------|-------|
| `-q` / `--quiet` | `ERROR` | Suppressed | No `event=*` info lines on the happy path; only error lines if any |
| _(default)_ | `INFO` | Live region (TTY) / plain logfmt per-phase (non-TTY) | The "normal" surface |
| `-v` / `--verbose` | `DEBUG` | Live region (TTY) / plain logfmt per-phase (non-TTY) | Reserved — no debug-level events emitted in v1.0 |
| `--debug` | `DEBUG` | Live region (TTY) / plain logfmt per-phase (non-TTY) | Same as `-v` plus the artifact directory of US-7 |

The three flags are mutually exclusive (SRS §9.1 `[-v | -q | --debug]`);
combining any two exits 2. On a non-TTY stderr (pipes, CI captures)
the bar is replaced by the logfmt event stream — same information,
no ANSI control sequences (AC-US-3.2).

## Observed throughput (no v1 SLA)

The project doesn't commit to a wall-clock target (NFR-1). Observed
end-to-end timings on the maintainer's reference machines, on the
bundled 60-second fixture:

| Backend / model | Hardware | First run (cold cache) | Steady state |
|-----------------|----------|------------------------|--------------|
| `faster-whisper` `tiny` | macOS Apple Silicon | ~30 s (~75 MB download) | ~7 s |
| `faster-whisper` `tiny` | Ubuntu CI runner (CPU) | ~30 s | ~10 s |
| `mlx-whisper` `tiny` | macOS Apple Silicon | (download then) ~5 s | ~5 s |

Numbers refresh whenever a release is cut. If your throughput differs
substantially, file an issue with the `event=done` summary line and the
output of `uname -a` — see Risk #7 in the project plan.

## Development

The project follows a three-tier test strategy (ADR-0017):

- **Tier 1 — unit + fakes.** Pure logic exercised against in-memory
  fakes; sub-second total. Default `pytest` invocation.
- **Tier 2 — contract.** `WhisperBackend` Protocol invariants run
  against `FakeBackend` AND each real backend (`faster-whisper`,
  `mlx-whisper`); real-backend parametrisations skip cleanly when
  their library is not importable. Marked `pytest.mark.contract` so
  the unit tier stays sub-second; CI runs Tier 2 on the Ubuntu +
  macOS-14 matrix.
- **Tier 3 — integration.** Full CLI on `examples/sample.mp3` with
  the real `faster-whisper` `tiny` model. Marked `pytest.mark.slow`
  so the unit tier stays sub-second.

```sh
uv run pytest                     # Tier 1 (default — sub-second)
uv run pytest -m contract         # Tier 2 (real backends on the host)
uv run pytest -m slow             # Tier 3 (real CLI on examples/sample.mp3)
uv run pytest -m "contract or slow or not slow"   # everything (CI does this)

uv run ruff check .               # lint
uv run ruff format --check .      # format
uv run mypy --strict src tests    # type check
```

The slow tier downloads the `tiny` model on first run (~75 MB). A
warning-as-error pytest policy is in effect — any unhandled Python
warning fails the suite (NFR-10 stderr cleanliness).

The architecture lives in
[`SYSTEM_DESIGN.md`](SYSTEM_DESIGN.md) and the 17 accepted ADRs under
[`docs/adr/`](docs/adr/); the requirements are in
[`SRS.md`](SRS.md); the sprint plan in
[`PROJECT_PLAN.md`](PROJECT_PLAN.md).

## Reporting issues

File anything that surprised you on the
[GitHub Issues tracker](https://github.com/invaderDMG/podcast-script/issues) —
bugs, install friction, output quality regressions, doc gaps. Please
include the env block (OS + chip, Python version, `uv` version,
`ffmpeg` version, project tag) and a copy-pasteable reproduction so
the report is actionable without a back-and-forth. The pre-v1.0.0
dogfooder phase is over per `PROJECT_PLAN.md` §8 (the historical
guide stays at [`docs/DOGFOODING.md`](docs/DOGFOODING.md) for
reference); from v1.0.0 onward this is a normal open-source backlog
triaged at the maintainer's cadence.

## License

MIT — see [`LICENSE`](LICENSE) for the full text. Declared canonically
via `[project] license = "MIT"` in `pyproject.toml`.

## Acknowledgements

- Bundled fixture speech: LibriVox _Las Fábulas de Esopo, vol. 01_ —
  public domain (LibriVox standard).
- Bundled fixture music bed: Musopen Complete Chopin Collection,
  Prelude Op. 28 No. 5 — CC0 1.0 Universal.
- Full attribution and SHA-256 checksums in
  [`examples/CREDITS.md`](examples/CREDITS.md).

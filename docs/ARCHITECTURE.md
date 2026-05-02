# Architecture

This is the four-bullet front door to the design. Each bullet names
the choice, the failure mode it avoids, and the ADR with the deeper
"why". Read top-to-bottom in five minutes; dig into the linked ADRs
when you need the alternatives-considered detail.

The four topics here are the ones `SRS.md` §16.2 fixes for v1.0;
nothing else belongs in this file. Per `SRS.md` §1.3, an
ADR-style "rejected alternatives" appendix is explicitly **out of
scope** for v1 — that material lives in the individual ADRs under
[`docs/adr/`](adr/).

---

## 1. Segment first, transcribe only the speech

The pipeline runs `inaSpeechSegmenter` over the decoded PCM **before**
any Whisper call, labels every second of audio as one of
`{speech, music, noise, silence}`, and feeds **only the speech
segments** through Whisper. Music regions become English markers in
the output Markdown (`> [MM:SS — music starts]` / `> [MM:SS — music
ends]`); noise and silence regions are dropped at render time
(see §3).

**The failure mode this avoids:** Whisper is a speech model, trained
on speech. On music it doesn't politely refuse — it hallucinates
plausible-but-fake "lyrics" with full confidence, sometimes for
minutes at a stretch. Running Whisper on the whole file (the simpler
two-step "decode → transcribe" pipeline) produces a transcript with
fabricated speech interleaved through every musical segment, and the
listener has no way to tell which lines are real. Segmenting first
is the only way to keep Whisper away from the inputs it's wrong on.

The orchestrator is a pipes-and-filters `Pipeline` class
(`src/podcast_script/pipeline.py`) with constructor-injected stages,
streaming one transcribe call per speech segment so a mid-loop
failure leaves the partial transcript usable in `--debug` artefacts.

**See also:** [ADR-0002](adr/0002-pipes-and-filters-pipeline.md)
(pipeline shape), [ADR-0004](adr/0004-streaming-per-segment-transcribe.md)
(per-segment streaming contract),
[ADR-0010](adr/0010-pipeline-level-progress-tick.md) (where the
`rich` progress bar ticks).

---

## 2. Two backends, one Protocol, one composition root

The transcribe step is fronted by a `WhisperBackend` Protocol
(`src/podcast_script/backends/base.py`) with two concrete
implementations: `FasterWhisperBackend` (CPU / Linux / Intel macOS)
and `MlxWhisperBackend` (Apple Silicon). `select_backend()` reads
`sys.platform` + `platform.machine()` and picks `mlx-whisper` for
`arm64-darwin`, else `faster-whisper`. `--backend faster-whisper`
always wins; `--backend mlx-whisper` off Apple Silicon raises
`UsageError` (exit 2) per UC-1 E7.

**The failure mode this avoids:** hard-coding either backend ties the
tool to one platform. `mlx-whisper` is the only path that uses Apple
Silicon's Neural Engine — without it, Apple Silicon users get
nothing better than CPU `faster-whisper`. `mlx-whisper` is also a
Darwin/arm64-only wheel (PEP 508 marker in `pyproject.toml`); a
hard-import would break `uv sync` on Linux. The Protocol abstraction
is also the testability seam ADR-0017's three-tier strategy depends
on — Tier 1 unit tests inject a `FakeBackend` and never load
`faster-whisper` or `mlx-whisper`.

Both real backends use lazy imports inside `load()` so a Tier 1
`pytest` run boots in <1 s without either heavy dep installed
(per [ADR-0011](adr/0011-lazy-imports-for-heavy-deps.md)). The
Protocol's behavioural invariants are pinned by Tier 2 contract
tests (`tests/contract/`) running identically against `FakeBackend`
and each importable real backend.

**See also:** [ADR-0003](adr/0003-whisper-backend-protocol.md)
(Protocol + platform rule), [ADR-0011](adr/0011-lazy-imports-for-heavy-deps.md)
(lazy-import boundary), [ADR-0017](adr/0017-three-tier-test-strategy.md)
(why the Protocol is the testability seam).

---

## 3. Segmenter covers every second; renderer drops two of four labels

The segment-merge module (`src/podcast_script/segment.py`) emits a
list of `Segment(start, end, label)` records that **cover every
second** of the input — gaps are filled with synthetic `silence`
segments, and the four-label vocabulary
(`speech` / `music` / `noise` / `silence`) is the only thing
downstream code accepts (NFR-3 ordering, NFR-4 coverage; pinned by
property tests in `tests/unit/test_segment_property.py`). The
renderer (`src/podcast_script/render.py`, the `_emit_segment` branch
near line 100) then **drops** `noise` and `silence` regions: they
exist in the structured layer (`segments.jsonl` under `--debug`)
but produce no lines in the user-facing Markdown.

**The failure mode this avoids:** without segmenter coverage, music
or non-speech regions slip through unannotated and Whisper sees them
(see §1's hallucination failure). Without the renderer drop, the
Markdown would be cluttered with `> [MM:SS — silence starts]` lines
between every utterance — not what podcast producers (the v1 actor
per `SRS.md` §3) want to read or re-publish. Splitting "must
classify" (segmenter responsibility, NFR-4) from "must render"
(renderer responsibility, AC-US-2.5) keeps each layer simple: the
segmenter doesn't decide visibility, the renderer doesn't decide
classification.

The split also keeps `--debug`'s `segments.jsonl` lossless: a
maintainer reproducing a bug can inspect the full noise/silence
classification, even though the user-facing Markdown drops them.

**See also:** `SRS.md` AC-US-2.5 (renderer drop) + NFR-4 (segmenter
coverage) + §Q7 (the resolved decision); `tests/unit/test_segment.py`
+ `tests/unit/test_segment_property.py` (the invariants pinned in
code). No ADR — this is a pure rendering policy decision recorded
in the SRS, not an architectural choice with structural alternatives.

---

## 4. All-or-nothing output via temp file + atomic rename

The final Markdown lands at the resolved output path via
`atomic_write()` (`src/podcast_script/atomic_write.py`). The helper
opens a tempfile in the **same directory** as the target
(`tempfile.NamedTemporaryFile(dir=path.parent, …, delete=False)`),
writes the full payload, `fsync`s the file, then calls
`os.replace(tmp_path, path)`. POSIX `rename(2)` is atomic on the
same filesystem (NFR-5 contract). On any failure before the
`os.replace`, the tempfile is unlinked in `finally`; any prior
`episode.md` at the target path is untouched (AC-US-6.3).

**The failure mode this avoids:** a non-atomic write — say, opening
the target path directly with `"w"` mode — leaves a partial Markdown
file at the resolved output path on any mid-run failure (SIGTERM,
OOM, decode crash, transcribe error). Subsequent re-runs would then
hit AC-US-6.1's refuse-overwrite gate without `--force` and the user
is locked out by their own broken file. Worse, the partial file
*looks* finished to a casual reader: there's no marker for
"transcription was interrupted at minute 12 of 47". Atomic rename
ensures the only two observable states are "no output" and "complete
output" — never "partial output that looks complete".

The contract is exercised at three test tiers: Tier 1 in
`tests/unit/test_atomic_write.py` (in-process exception cleanup),
Tier 2 nothing specific (the helper has no Protocol surface),
and Tier 3 in `tests/integration/test_failure_injection.py`
(POD-034 — spawns the CLI as a real subprocess, SIGTERMs it
mid-transcribe, asserts no output landed and no `*.tmp` debris
survives). Together those pin the design rather than just the
implementation: any refactor that opened a tempfile during
transcribe (rather than near the end of `Pipeline.run`) would fail
the Tier 3 `*.tmp`-debris assertion.

**See also:** [ADR-0005](adr/0005-atomic-output-via-temp-and-rename.md)
(decision + alternatives); `SRS.md` NFR-5 (the contract this honours)
+ AC-US-6.3 (the user-visible AC); POD-009 (implementation),
POD-034 (failure-injection test).

---

## Pointers for further reading

- **Module layout:** `src/podcast_script/` — see
  [ADR-0007](adr/0007-flat-src-package-layout.md) for the decision
  log, `SYSTEM_DESIGN.md` §3.1 for the current map.
- **All ADRs:** `docs/adr/` — 17 accepted ADRs as of v1.0; the
  index is in [`docs/adr/README.md`](adr/README.md).
- **Test strategy:** [ADR-0017](adr/0017-three-tier-test-strategy.md)
  + `tests/{unit,contract,integration}/` (the shape was finalised
  in POD-029).
- **Error → exit-code mapping:**
  [ADR-0006](adr/0006-error-to-exit-code-via-typed-exceptions.md);
  user-visible table is in `README.md` "Exit codes".
- **Locked log-event catalogue:**
  [ADR-0012](adr/0012-event-catalogue-freeze.md); the 22 tokens are
  the SemVer-tracked grep contract from v1.0 onwards.

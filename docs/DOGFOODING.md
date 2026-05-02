# Dogfooding `podcast-script` v0.1.1

You've been invited to test `v0.1.1` ahead of the `v1.0.0` release. This
guide walks you through what's being asked, what the success bar looks
like, and how to file feedback that actually moves the project forward.

If anything in this guide is unclear, **that itself is a finding worth
reporting** — the bar set in `PROJECT_PLAN.md` §8 / Q7 is *"did the
README quickstart get them to a transcript without help?"*. If you
need to DM the maintainer to make the tool work, that's a doc bug.

---

## TL;DR — what you're agreeing to

- **Time commitment.** ~30–60 minutes for one full pass. You're not
  signing up for ongoing maintenance.
- **What you'll do.** Follow `README.md` end-to-end on the bundled
  fixture, then run the tool on a real podcast episode of your own,
  then file at least one GitHub issue with what you found.
- **What you need.** A macOS or Linux machine with ~3 GB free disk,
  a network connection (for the first-run model download), and a
  10–30 minute MP3 / audio file from a podcast you've worked on.
- **Where feedback goes.** GitHub Issues — `https://github.com/invaderDMG/podcast-script/issues`. No DMs, no email, no
  surveys (per `PROJECT_BRIEF.md` §17).
- **Your tag is `v0.1.1`.** Not `main`. Pinning to the tag means
  every dogfooder is testing the exact same surface and your feedback
  is comparable.

If that fits your week, read on. If it doesn't, that's also fine —
saying so is more useful than committing and ghosting.

---

## Before you start — prerequisites

You need:

- **OS:** macOS 14+ or a recent Ubuntu / Debian. Windows isn't a
  supported platform in v1 (POSIX signal handling, `ffmpeg`-via-PATH,
  and the file-locking semantics behind atomic write all assume
  POSIX).
- **Python 3.12 or newer.** Check with `python3 --version`. If you're
  on 3.11 or older, install 3.12 — `uv` can do that for you in the
  next step, but you may want a system-managed install.
- **Disk space:**
  - ~75 MB if you only run the `tiny` model (smoke-test only).
  - ~1.5 GB if you want `medium` (recommended for evaluation).
  - ~3 GB if you want `large-v3` (production quality, Apple Silicon
    only — `mlx-whisper` won't run on Linux or Intel Mac).
- **Network connection** for the first run. The chosen Whisper model
  downloads from the Hugging Face Hub on first invocation; subsequent
  runs are offline. The `inaSpeechSegmenter` library also fetches a
  small model on first install — same story.
- **An audio file you actually want to transcribe.** Ideally 10–30
  minutes of your own podcast (or a public-domain episode you've
  worked on). MP3, WAV, M4A, FLAC, OGG all work — anything `ffmpeg`
  can decode. The point of dogfooding is "does this work on *your*
  audio?", not "does this work on the author's fixture".

If any of these are blockers (e.g. you're on Windows, or you don't
have time to do a 30-minute episode test), file an issue with the
title `[dogfood] blocker: <reason>` and stop here — that itself is
useful feedback.

---

## Step 1 — Install

Three system bits, then the project:

```sh
# (1) uv — Python package manager. One-time install.
curl -LsSf https://astral.sh/uv/install.sh | sh
# Restart your shell or run: source $HOME/.local/bin/env

# (2) ffmpeg — audio decoder. Required at runtime.
brew install ffmpeg              # macOS
sudo apt-get install ffmpeg      # Debian / Ubuntu

# (3) the project itself. Pin to v0.1.1 — not main.
git clone https://github.com/invaderDMG/podcast-script.git
cd podcast-script
git checkout v0.1.1              # important — pin the surface
uv sync                          # creates .venv with locked deps
```

**Sanity check** — confirm the CLI is reachable:

```sh
uv run podcast-script --help
```

You should see the flag list. If `uv run` errors with "command not
found" or `uv sync` failed, **stop and file an issue** — this is
exactly the install-doc gap Q7 is meant to surface.

---

## Step 2 — Smoke test on the bundled fixture

Before you point the tool at your own audio, verify the install works
end-to-end on the test fixture that ships with the repo:

```sh
uv run podcast-script examples/sample.mp3 \
    --lang es --model tiny --backend faster-whisper \
    -o /tmp/sample.md
```

What to expect:

- A `rich` progress bar with three named phases (decode / segment /
  transcribe), or — if your terminal is piped — plain logfmt event
  lines on stderr (`event=startup` ... `event=done`).
- The first run downloads the `faster-whisper tiny` model
  (~75 MB). A `event=model_download` line fires within ~1 second of
  startup so you know it's working, not hung. Subsequent runs are
  instant from cache.
- An output file at `/tmp/sample.md` shaped roughly like:

  ```markdown
  `00:01`  Las fabulaste es opo,

  `00:03`  grabado para librevox.org por Christina Chu.

  > [00:25 — music starts]
  > [00:35 — music ends]
  ```

If this works: great, your environment is good. **Move to Step 3.**

If it doesn't: file an issue with the title `[dogfood] smoke test
failed: <one-line summary>` and include:

- Your OS + chip (`uname -a`).
- The full stderr output of the run.
- The exit code (`echo $?` after the failed run).

The smoke test failing is the most valuable possible finding — it
means a real user will hit the same wall.

---

## Step 3 — Run it on your own audio

This is the actual dogfooding bit.

Pick an episode (10–30 min ideal — long enough to have music
transitions, short enough to not eat your afternoon). Pick a model:

- **`medium`** is the recommended starting point for evaluation —
  good quality on CPU, ~1.5 GB download, real-world speeds.
- **`large-v3`** if you're on Apple Silicon and want production
  quality — uses `mlx-whisper` automatically.
- Avoid `tiny` and `base` for evaluation; they're noisy by design
  (intended for smoke tests, not assessment).

```sh
# Replace path/to/your/episode.mp3 with a real file.
uv run podcast-script ~/path/to/your/episode.mp3 \
    --lang es \
    --model medium \
    -o ~/Desktop/episode-transcript.md
```

(Substitute `--lang es` with one of the eight supported codes:
`es / en / pt / fr / de / it / ca / eu`. If your podcast is in a
language outside that set — `ja`, `zh`, `ru`, etc. — file an issue
saying so; that's a v1 limitation we should know is hurting you.)

Watch what happens:

- Did the progress bar render correctly?
- Did `event=transcribe_start` fire and ticks advance?
- Did the run complete? Exit code 0?
- How long did it take? (Compare to the "Observed throughput" table
  in `README.md` — flag if you're substantially slower.)

When done, **open the output Markdown** and read it. Read it like
you're going to publish it.

---

## Step 4 — Evaluate

Open `~/Desktop/episode-transcript.md` (or wherever you sent the
output) and answer these as you read:

### Transcript quality

- Is the speech text accurate enough to publish? Where it's wrong,
  is it the kind of wrong you can fix with `grep` / find-replace,
  or the kind that needs a re-listen?
- Are there obvious word-boundary glitches (`fabulaste` instead of
  `fábulas` in the smoke test, e.g.)?
- Did the language code (`--lang es`) actually constrain Whisper, or
  did it switch into a wrong language partway through?

### Music markers

- Are the music regions in your episode marked? Did the marker
  timestamps line up with what you remember (~1-2 second tolerance
  is normal)?
- Were there music regions the tool *missed*? Quiet music under
  speech is the documented blind spot (`README.md` § "Accuracy
  caveats", EC-1) — note any examples.
- Were there false positives — text-only regions marked as music?

### Output format

- Are the timestamps the format you expected (`MM:SS` for episodes
  under an hour, `HH:MM:SS` for an hour or more)?
- Does the Markdown render correctly in your editor / preview tool?
- Is the structure useful for your downstream workflow (publishing
  to your podcast platform, importing into a CMS, etc.)?

### UX

- Was anything in the install process unclear?
- Did the progress bar give you confidence the tool was making
  progress? Did the first-run download notice fire fast enough that
  you didn't think it had hung?
- Were any error messages cryptic or unhelpful?
- Anything you tried to do that the tool refused, that surprised
  you?

You don't need to write a 10-page review. Three or four bullet points
covering "what worked, what didn't, what surprised me" is exactly
right.

---

## Step 5 — File feedback

**Where:** GitHub Issues only — `https://github.com/invaderDMG/podcast-script/issues`. Per `PROJECT_BRIEF.md` §17, this is the
canonical channel; no DMs, no email, no surveys.

**Title prefix:** start with `[dogfood]` so the maintainer can
distinguish dogfooder findings from issues filed later by general
users. Examples:

- `[dogfood] smoke test failed on macOS 15.2 — ffmpeg version mismatch`
- `[dogfood] missed music marker at 12:47 (intro fade-out under VO)`
- `[dogfood] medium model: transcript quality unusable for editorial publishing`
- `[dogfood] install: 'uv sync' failed without ffmpeg on PATH and the error message wasn't clear`
- `[dogfood] positive: ran the README quickstart end-to-end without help in <20 minutes`

The last shape is genuinely useful — Q7's acceptance bar is "did the
README quickstart work without help?" and a confirmation issue
explicitly answers it.

### What to include in a bug-shaped issue

For anything that crashed or misbehaved, include:

```markdown
## Environment
- OS + chip: <output of `uname -a`>
- Python: <output of `python3 --version`>
- uv: <output of `uv --version`>
- ffmpeg: <output of `ffmpeg -version | head -1`>
- Project version: v0.1.1 (commit <output of `git rev-parse HEAD`>)

## Reproduction
The exact CLI invocation:
\`\`\`sh
uv run podcast-script <args>
\`\`\`

## Expected
<what you thought would happen>

## Actual
<what happened — paste the full stderr; logfmt is grep-friendly>

## Audio
<any sharable detail — duration, language, music density. Don't
upload the audio itself unless the issue is genuinely audio-content-
specific>
```

For a crash specifically — re-run with `--debug` and attach (or
sanitise + paste) the contents of `<input-stem>.debug/`:

- `decoded.wav` — usually skip; it's the input as PCM.
- `segments.jsonl` — the `inaSpeechSegmenter` output. Useful if
  music markers are wrong.
- `transcribe.jsonl` — partial transcript, line-flushed. Useful if
  the run died mid-transcribe.
- `commands.txt` — the exact `ffmpeg` argv used. Useful if decode
  failed.

### What to include in a quality-shaped issue

For "the transcript was bad" / "the markers were wrong" / "this UX
confused me", a free-form report is fine. Helpful:

- A few specific timestamps where the issue shows up.
- The language + model combination you ran.
- One or two-line excerpts of what you expected vs. what you got.
- Whether the issue reproduced if you re-ran with the same
  invocation.

---

## What's already known and *not* a bug

To save you (and the maintainer) cycles, these are documented v1
limitations — please don't file issues for them unless you have
specific data showing they're worse than the docs imply:

- **Quiet music under speech may not be marked** (`README.md` §
  "Accuracy caveats", EC-1, R-2). The segmenter is energy-based; a
  music bed quieter than the voice over it can read as pure speech.
  Specific cases where this hurts your workflow are valuable
  signals; "this happened once" probably isn't.
- **`tiny` and `base` produce noisy text.** They exist for smoke
  tests. If you used them for evaluation, that's the bug.
- **No batch / glob / directory input.** One file per invocation,
  by design (SRS §1.3 Out of scope).
- **No auto language detection.** `--lang` is required; eight codes
  only. Adding a code is a docs+test PR for v2, not a bug in v1.
- **Single voice / no diarization.** v1 doesn't separate speakers.
  Output is one continuous speech stream interleaved with music
  markers. Speaker labels are explicit non-goals.
- **No GUI.** CLI only.
- **Mid-run interruption produces no partial output.** This is the
  atomic-write contract (NFR-5 / AC-US-6.3); a failed run leaves
  any prior `episode.md` byte-for-byte intact, but the in-flight
  run produces *nothing* on the output path. Restart from scratch.
- **macOS Apple Silicon vs. Linux backend split.** `mlx-whisper`
  on Apple Silicon (uses the Neural Engine), `faster-whisper`
  everywhere else. `--backend mlx-whisper` on a non-Apple-Silicon
  machine exits 2 by design.
- **Anything in the locked CLI grammar / 22-token event catalogue /
  exit-code policy.** Those are documented v1 contracts (`SRS.md`
  §16.1); changes happen at major-version bumps, not in response
  to feedback. Liking-or-disliking the names is fine to mention,
  not a v1 fix.

---

## Pass / fail — the Q7 acceptance bar

Per `PROJECT_PLAN.md` §8, the dogfooder phase passes when *"at least
one external dogfooder has run the quickstart end-to-end without
help, before the v1.0.0 tag"*. Concretely:

- ✅ **Pass:** you cloned the repo at `v0.1.1`, ran `uv sync`, ran
  the quickstart on your own audio, got a transcript out, and filed
  at least one issue (positive or negative). You did this without
  needing to DM the maintainer.
- ❌ **Fail:** you got stuck somewhere and had to ask for help to
  unstick. The "fail" outcome **is the point of dogfooding** — it
  tells the maintainer the README has a hole. File an issue
  describing exactly where you got stuck.

There's no third state. "I tried and gave up" without filing
anything is the worst outcome — silently failing tells the
maintainer nothing.

---

## After v1.0.0

Once v1.0.0 ships, the dogfooder phase is over and the project goes
to `Public` user-testing per `PROJECT_PLAN.md` §8 (anyone who picks
up the repo, GitHub Issues triaged at sprint planning). Your
dogfooder issues are **not** retroactively converted to support
tickets — the issue tracker becomes a normal open-source backlog,
and issues that were dogfooder-specific framings ("this confused me
when I was the first person to try this") may be closed as resolved
or out-of-scope based on whether the underlying problem still
applies.

If you wanted to keep contributing post-v1.0.0 — patches, more
issues, helping triage — that's welcome. The maintainer will reach
out separately if there's a fit.

---

## Acknowledgements

Thank you for the time. The maintainer-bus-factor risk
(`PROJECT_PLAN.md` §10 R-9) is real for a solo project, and external
dogfooding is one of the structural mitigations. Your "this confused
me" is more valuable than your "this worked great" — both kinds of
feedback help, but the former is what closes the gap between "the
maintainer can use it" and "anyone who follows the docs can use it".

---

## For the maintainer — invitation template

If you (the maintainer) are reading this, here's a copy-paste-ready
DM for inviting a dogfooder. Replace `{NAME}` with their name and
adjust as needed:

> Hey {NAME} — I just shipped `v0.1.1` of a small CLI tool I've been
> building, `podcast-script`. It segments podcast audio into speech
> vs. music regions and runs Whisper only on the speech (so no
> hallucinated "lyrics" over your music beds). I'm looking for one
> or two podcast producers to dogfood it on a real episode of theirs
> before I cut `v1.0.0`.
>
> Time commitment is about an hour: install, run on the bundled
> fixture, run on something of yours, file an issue with what you
> found.
>
> Repo + dogfooder guide:
> https://github.com/invaderDMG/podcast-script/blob/v0.1.1/docs/DOGFOODING.md
>
> Pin to the `v0.1.1` tag so everyone's testing the same surface.
> No worries if it's not your week — saying so is more useful than
> committing and ghosting.

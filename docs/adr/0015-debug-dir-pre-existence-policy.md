# ADR-0015: `--debug` artifact directory pre-existence policy

- **Status:** Accepted
- **Date:** 2026-04-25
- **Deciders:** Solo maintainer
- **Supersedes:** —

## Context
`SRS.md` US-7 / AC-US-7.1 specifies that under `--debug`, an `<input-stem>.debug/` directory exists next to the input after a run, containing `decoded.wav`, `segments.jsonl`, `transcribe.jsonl`, `commands.txt`. The SRS does not specify behaviour when that directory already exists from a prior run.

This is the same shape of decision as US-6 for the output Markdown file: re-running the tool finds prior artifacts on disk; the question is whether to silently destroy them, error out, or accumulate.

`SRS.md` US-6 / AC-US-6.1 picks "refuse + opt-in via `--force`" for the output Markdown — that's the project's stated principle: **the tool never silently destroys prior work**. Two ways of expressing the same principle inside one tool would be confusing for users and for the design itself.

## Decision
The `--debug` artifact directory follows the **same policy as the output Markdown file**:

1. If `<input-stem>.debug/` does not exist → create it and proceed.
2. If it exists and `--force` is not set → raise `OutputExistsError` (exit code 6, `event=output_exists`) with a stderr message naming the existing directory and instructing the user to pass `--force` to overwrite (mirror of AC-US-6.1).
3. If it exists and `--force` is set → `shutil.rmtree(<input-stem>.debug/)` then `mkdir(<input-stem>.debug/)`, proceed normally.

The pre-existence check happens in the same validation block as the output-Markdown check (UC-1 step 3), so both refusals are reported at the same point in the run — well before any backend or decode work — and both reuse the same exit code (6) and event token (`output_exists`).

The error message uses the directory path explicitly so the user understands which artifact is blocking: `error: <input-stem>.debug/ already exists; pass --force (-f) to overwrite (or omit --debug)`.

## Alternatives considered
- **Auto-overwrite (rmtree + recreate) every run** — rejected: silently destroys prior debug artifacts the user may have been about to inspect. Violates the project principle expressed in US-6.
- **Timestamp-suffix on each run** (`<stem>.debug.20260425T173002/`) — rejected: pollutes the input directory with one new dir per debug run; users running 20 iterations of `--debug` accumulate 20 directories no one ever cleans up. Hard to wire into the lazy-import / atomic-write flow cleanly.
- **Append-and-overwrite individual files** (keep the directory; overwrite files we write this run, leave others untouched) — rejected: awkward semantics — what if the segment count differs across runs? Stale `transcribe.jsonl` lines past the new end are misleading. The whole point of the artifact dir is "what did *this* run produce", not "merge of every run that ever happened".

## Consequences
- **Positive:** consistent with US-6 — one mental model for the user ("the tool never destroys prior work without `--force`"). Reuses exit code 6 and the `output_exists` event token (no new exit code, no catalogue churn). Refusal happens at validation time, fast-fail.
- **Negative:** users iterating with `--debug` repeatedly will type `--force` (or `-f`) often. Acceptable — the use case for repeated `--debug` runs is bug reproduction, where typing `-f` is the intentional cost of opting into destructive overwrite.
- **Neutral:** the validation block is now responsible for two pre-existence checks instead of one; both can fire the same way, and the message is specific to which artifact triggered the refusal.

## Related
- ADR-0005 (atomic output — same "never destroy prior work" principle)
- ADR-0006 (typed exceptions — `OutputExistsError` reused)
- ADR-0012 (event catalogue — `output_exists` token reused)
- `SRS.md` US-6, US-7, AC-US-6.1, AC-US-7.1, AC-US-7.2
- `SYSTEM_DESIGN.md` §2.5, §4.3

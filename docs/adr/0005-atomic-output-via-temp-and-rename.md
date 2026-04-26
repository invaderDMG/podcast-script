# ADR-0005: Atomic output via temp file + rename

- **Status:** Accepted
- **Date:** 2026-04-25
- **Deciders:** Solo maintainer
- **Supersedes:** —

## Context
`SRS.md` NFR-5 requires that the tool exit 0 only when a complete, well-formed Markdown file has been written to the resolved output path; if any phase fails, no partial file may exist at that path. AC-US-6.3 reinforces this for the `--force` overwrite path: the previous `episode.md` must be preserved if the run fails between starting and finishing.

The transcribe phase can run for many minutes (multi-hour episode + `large-v3` on CPU). A user pressing Ctrl-C, a backend crash, or a power loss mid-write must not leave a half-Markdown file at the user's expected output path.

`SRS.md` Risk T1 (path injection / arbitrary write) further constrains where we are allowed to create files.

## Decision
Write the transcript via a **temp file in the same directory as the resolved output path, followed by `os.rename` on success**:

1. Compute the resolved output path `final = <input_dir>/<input_stem>.md` (or `-o <path>`).
2. Validate `final.parent` exists (else `InputIOError`, exit 3 — `SRS.md` E6).
3. If `final` exists and `--force` is not set → `OutputExistsError` (exit 6) before any work.
4. After render produces the full Markdown string, open a temp file with `tempfile.NamedTemporaryFile(dir=final.parent, prefix=final.stem + ".", suffix=".md.tmp", delete=False)`, write, fsync (best-effort), close.
5. `os.replace(tmp_path, final)` — atomic on POSIX when source and destination are on the same filesystem; this is guaranteed because the temp file is created in `final.parent`.
6. On any exception between step 4 and step 5, the temp file is `unlink()`-ed in a `finally` block; the pre-existing `final` (if any) is unchanged.
7. After a successful `os.replace`, open `final.parent` and `os.fsync(dir_fd)` so the rename's directory-entry change is durable across a power loss. Best-effort, matching step 4's file-fsync policy: failures (e.g. on filesystems that don't support directory fsync) are swallowed. Added in v1.1 (PR #7) as defense-in-depth; NFR-5 was already satisfied without it.
8. If `final` existed before the rename, capture its mode via `os.stat(final).st_mode` before step 4 and `os.chmod(final, prior_mode)` after step 5. `tempfile.NamedTemporaryFile` creates the temp at `0o600`, so without restoration a `--force` rerun would silently demote a user's `chmod 644 episode.md`. Added in v1.1 (PR #7).

The temp filename includes the input stem and a `.tmp` suffix so a stray temp file (left after a process kill -9, where Python `finally` doesn't run) is recognizable and ignorable by humans.

The same-directory-as-output rule is required for atomicity: cross-filesystem renames are not atomic and may fall back to copy + unlink, which violates the atomicity contract.

## Alternatives considered
- **Write directly to the final path** — rejected: violates NFR-5; partial file on any mid-run failure.
- **Temp file in `/tmp` then move** — rejected: `/tmp` is often a separate filesystem, breaking the atomic-rename guarantee.
- **`os.rename` instead of `os.replace`** — rejected: `os.rename` raises on Windows if the target exists; `os.replace` is the correct cross-platform choice (`SRS.md` says Windows is unsupported in v1, but using `os.replace` costs nothing and future-proofs).

## Consequences
- **Positive:** atomic guarantee holds on POSIX; existing `episode.md` is never destroyed by a failed run; users iterating on flags don't lose previously hand-edited transcripts (US-6).
- **Positive (v1.1):** prior file mode is preserved across `--force` reruns (step 8); the rename itself is durable across power loss (step 7).
- **Negative:** rare-case clutter — a `kill -9` mid-write may leave `<input_stem>.<rand>.md.tmp` next to the input; humans recognize and delete. We do not auto-clean stale tmp files on subsequent runs (out of scope).
- **Neutral:** `fsync` before rename is best-effort; we don't fail the run if `fsync` errors (rare on local FS). Same policy applies to the parent-directory fsync added in step 7.

## Related
- ADR-0002 (Pipeline orchestrator — owns the temp+rename code)
- `SRS.md` NFR-5, AC-US-6.1, AC-US-6.2, AC-US-6.3, AC-US-6.4, E1, E3, E6
- `SRS.md` §11 T1
- `SYSTEM_DESIGN.md` §2.4, §3.7 (cleanup on failure)

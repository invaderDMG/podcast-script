# ADR-0014: SIGINT / KeyboardInterrupt handling

- **Status:** Accepted
- **Date:** 2026-04-25
- **Deciders:** Solo maintainer
- **Supersedes:** —

## Context
The transcribe phase routinely runs for many minutes (multi-hour episode + `large-v3` on CPU). Users *will* press Ctrl-C — for example after starting the wrong file, or to abort a slow first-run download. Python translates SIGINT to a `KeyboardInterrupt` exception raised at the next bytecode boundary; Python's default behaviour on uncaught `KeyboardInterrupt` is to exit with code 130 (128 + SIGINT).

`SRS.md` NFR-9 locks the documented exit codes to the set `{0, 1, 2, 3, 4, 5, 6}`. Exit 130 is not in the contract, and `SRS.md` Risk #8 explicitly warns that the code set becomes a shell-script integration contract once published. Letting Python exit 130 by default would create an undocumented "real" exit code that grows around the contract over time.

`SRS.md` AC-US-5.3 already specifies the desired Ctrl-C behaviour for the model-download case ("the tool resumes or restarts the download cleanly and does not leave a half-loaded model in use"); `huggingface_hub` handles that automatically. The remaining gap is the rest of the pipeline: temp-file cleanup (ADR-0005's `finally` block already covers it as long as the exception unwinds normally), `--debug` directory state (US-7 wants partial artifacts preserved on any kind of abort), and the exit code itself.

## Decision
**Catch `KeyboardInterrupt` at the outermost `try` block in `cli.py`** — the same block that catches `PodcastScriptError` (ADR-0006) — and translate it to:

```python
def main(...):
    try:
        Pipeline(...).run(config)
    except KeyboardInterrupt:
        log.warning(event="internal_error", code=1, cause="interrupted by user")
        raise typer.Exit(1)
    except PodcastScriptError as e:
        ...
    except Exception as e:
        ...
```

This produces:

- **Exit code 1** — the generic `internal_error` slot in NFR-9. Shell scripts wrapping the tool can rely on the tool only ever exiting in `{0..6}`; a Ctrl-C looks like "something went wrong, retry maybe", which is a fair classification.
- **Stage-level `finally` blocks still run** — `KeyboardInterrupt` is caught at the top, not inside stages, so unwinding through stage code triggers all `finally` blocks normally. The atomic-write temp file is unlinked (ADR-0005). The `<input-stem>.debug/` directory is left intact (US-7 — partial JSONL files are exactly what a user reproducing a bug wants).
- **`huggingface_hub` cleanup** — the library catches its own `KeyboardInterrupt` mid-download and either persists the resumable partial or unlinks; we surface its terminal behaviour as-is (AC-US-5.3).
- **`level=warn`** rather than `level=error` because the user opted in — this isn't a failure of the tool, it's the user's choice. The `event=internal_error` token (from the frozen catalogue, ADR-0012) and `code=1` keep the log shape consistent with other terminal failures.

The catch is at the outermost layer so a stage cannot accidentally swallow a `KeyboardInterrupt` and continue running; if a future contributor adds a stage with broad `except Exception`, the typed-exception convention (ADR-0006) prevents them from catching `KeyboardInterrupt` (which derives from `BaseException`, not `Exception`).

## Alternatives considered
- **Let `KeyboardInterrupt` propagate naturally; exit 130** — rejected: violates NFR-9's exit-code contract; shell scripts wrapping the tool would have to special-case 130 separately from the documented set.
- **Install a `signal.signal(SIGINT, …)` handler that sets a "cancel" flag stages poll** — rejected: cooperative cancellation has no benefit when the dominant blocker (Whisper inference inside `backend.transcribe()`) is uninterruptible mid-call from Python; the polling adds code without changing behaviour.
- **Add a new exit code `7 — interrupted`** — rejected: cleanest semantically, but breaks NFR-9's locked 0–6 set, would require an SRS amendment, and elevates Ctrl-C to a documented exit class for a behaviour that doesn't really need its own slot.

## Consequences
- **Positive:** NFR-9's contract holds without exception; users get a predictable exit 1 + log line on Ctrl-C; `--debug` artifacts survive for inspection; temp file is cleaned. The behaviour is testable: `pytest` can `pytest.raises(typer.Exit) as e; assert e.value.exit_code == 1` after raising `KeyboardInterrupt` inside a fake stage.
- **Negative:** users who specifically expected exit 130 (Unix convention) won't get it; we trade convention for contract stability. Documented in README as a deliberate choice.
- **Neutral:** `level=warn` for user-initiated abort is a small departure from "every error event is `level=error`"; the catalogue (ADR-0012) doesn't constrain `level`, only `event` token names, so this is fine.

## Related
- ADR-0005 (atomic write — `finally` cleanup path)
- ADR-0006 (typed exceptions — outermost CLI catch shape)
- ADR-0012 (event catalogue — `internal_error` token)
- `SRS.md` NFR-9, AC-US-5.3, US-7, Risk #8
- `SYSTEM_DESIGN.md` §3.7, §3.8, §5 Risk #8 (closed)

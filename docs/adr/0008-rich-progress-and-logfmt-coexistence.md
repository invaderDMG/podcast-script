# ADR-0008: Coexisting `rich` progress + logfmt logs on stderr via `Progress.console`

- **Status:** Accepted
- **Date:** 2026-04-25
- **Deciders:** Solo maintainer
- **Supersedes:** —

## Context
`SRS.md` NFR-10 requires every stderr log line to be logfmt (key=value) and includes the `rich` progress bar as an explicit exception ("the `rich` progress bar is exempt from this requirement; it is a UI element, not a log stream"). `SRS.md` AC-US-3.1–3.3 require the progress bar to render on TTY stderr, degrade to one-line-per-phase on non-TTY (AC-US-3.2), and be suppressed under `--quiet` (AC-US-3.3).

Both streams target stderr. A naive setup — `logging.StreamHandler(sys.stderr)` plus `rich.progress.Progress(file=sys.stderr)` — will visibly clobber the live progress bar with newline-flushed log lines, because `rich`'s live display uses ANSI cursor movement that assumes nobody else is writing to the same TTY.

`SRS.md` Risk #9 separately calls log-line stability an implicit contract: the set of `event=…` tokens emitted at default verbosity is what users will grep for. The format must be predictable.

## Decision
Route the standard `logging` `Handler` through `rich.progress.Progress.console`:

```python
# logging_setup.py (sketch)
from rich.console import Console
from rich.logging import RichHandler
import logging

def configure(verbosity: Verbosity, progress: Progress | None) -> logging.Logger:
    console = progress.console if progress else Console(stderr=True, no_color=...)
    handler = RichHandler(
        console=console,
        show_time=False,        # logfmt embeds time itself if/when needed
        show_level=False,       # we put level=… in the formatted message
        show_path=False,
        markup=False,           # plain logfmt, no rich markup interpretation
        rich_tracebacks=(verbosity == "debug"),
    )
    handler.setFormatter(LogfmtFormatter())  # produces "level=info event=… …"
    logger = logging.getLogger("podcast_script")
    logger.addHandler(handler)
    logger.setLevel(level_for(verbosity))
    return logger
```

Key points:

1. **One Console object per process**, owned by the `Progress` if one is live, otherwise a plain `Console(stderr=True)`. Both the progress UI and the log handler write through it, so `rich` knows to redraw the bar after a log line lands.
2. **The `Formatter` is ours** (`LogfmtFormatter`) — `RichHandler` is purely the rendering channel; the on-stderr bytes are still logfmt, so NFR-10 holds and grep works as expected.
3. **`markup=False`** prevents `rich` from interpreting `[brackets]` in logfmt values as markup tags (logfmt values can contain `=`, spaces in quoted strings, but not Rich markup — explicitly disabling avoids surprises).
4. **`--quiet`** sets the logger level to `ERROR` AND constructs no `Progress` (AC-US-3.3); `--quiet` runs do not instantiate `rich` live displays at all.
5. **Non-TTY stderr** (`AC-US-3.2`): construct `Progress` with `disable=not sys.stderr.isatty()` (or use `Progress`'s built-in transient/disable behaviour), and emit a single `level=info event=<phase>_start` / `event=<phase>_done` log line per phase as the plain-text fallback. The `rich` console does not print ANSI to a non-TTY by default, but the explicit guard removes any ambiguity.
6. **Under `--debug`**, `RichHandler.rich_tracebacks=True` gives a styled traceback; otherwise unhandled exceptions bypass `RichHandler` and emit a single logfmt error line via the CLI catch (ADR-0006).

The fix is small (≈30 LOC in `logging_setup.py` plus a `LogfmtFormatter` class) but load-bearing for the user-facing feel of the tool.

## Alternatives considered
- **Two independent stderr writers** (`logging.StreamHandler(sys.stderr)` + `Progress(file=sys.stderr)`) — rejected: the progress bar visibly tears every time a log line arrives. Nobody ships this.
- **Suppress info/debug logs while progress is live** (only emit on phase boundaries) — rejected: makes `--verbose` pointless during the transcribe phase, which is most of the wall-clock time. Also fails AC-US-3.5's expectation that `--verbose` shows debug-level lines throughout.
- **Separate file descriptors** (logs to fd 3, progress to stderr) — rejected: requires shell wizardry to capture; breaks the convention "tool writes logs to stderr"; not a real option.

## Consequences
- **Positive:** the user sees a clean live progress bar with log lines flowing above it, exactly like modern CLI tools (`uv`, `cargo`, `bun`). NFR-10 holds because the Formatter is ours. `--quiet` and non-TTY paths are explicitly handled.
- **Negative:** introduces a coupling between `progress.py` and `logging_setup.py` (the `Progress` instance must exist before logging is configured if one is going to exist). Mitigation: a small factory in `cli.py` constructs both in the right order; tests use a stub `Console`.
- **Neutral:** `RichHandler`'s presence pulls in a bit more of `rich` than strictly necessary, but `rich` is already a dependency.

## Related
- ADR-0006 (Error hierarchy — error logging path that bypasses RichHandler)
- `SRS.md` NFR-10, AC-US-3.1, AC-US-3.2, AC-US-3.3, AC-US-3.4, AC-US-3.5, Risk #9
- `SYSTEM_DESIGN.md` §2.9, §4.4

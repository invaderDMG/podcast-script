# ADR-0006: Error → exit-code mapping via typed exception hierarchy

- **Status:** Accepted
- **Date:** 2026-04-25
- **Deciders:** Solo maintainer
- **Supersedes:** —

## Context
`SRS.md` NFR-9 locks seven exit codes (0/1/2/3/4/5/6) and `SRS.md` Risk #8 calls them an implicit shell-script contract — once published in `--help` and README, changing them is a breaking change. UC-1 enumerates exception flows E1–E9, each mapped to a specific code.

The tool needs a single source of truth for the exception → exit code mapping. Spreading `sys.exit(N)` calls across stages would scatter the contract and make it easy for a refactor to silently change a code.

## Decision
Define a **typed exception hierarchy** in `src/podcast_script/errors.py`. Each exception class carries its exit code as a class-level attribute:

```python
class PodcastScriptError(Exception):
    exit_code: int = 1
    event: str = "error"  # used as event=… in the logfmt error line

class UsageError(PodcastScriptError):
    exit_code = 2
    event = "usage_error"

class InputIOError(PodcastScriptError):
    exit_code = 3
    event = "input_io_error"

class DecodeError(PodcastScriptError):
    exit_code = 4
    event = "decode_error"

class ModelError(PodcastScriptError):
    exit_code = 5
    event = "model_error"

class OutputExistsError(PodcastScriptError):
    exit_code = 6
    event = "output_exists"
```

**Stages raise typed exceptions; they never call `sys.exit()` and never reference exit-code integers directly.** The CLI module is the only place that catches exceptions and translates:

```python
def main(...):
    try:
        Pipeline(...).run(config)
    except PodcastScriptError as e:
        log.error(event=e.event, code=e.exit_code, cause=str(e))
        raise typer.Exit(e.exit_code)
    except Exception as e:
        log.error(event="internal_error", code=1, cause=str(e))
        if config.verbosity == "debug":
            raise  # show traceback
        raise typer.Exit(1)
```

Tests assert on the exception type, not the integer, e.g. `pytest.raises(DecodeError)` — and a separate parametrized test `test_exit_codes_are_stable` asserts each class's `exit_code` matches NFR-9. Changing an integer requires updating that test, which makes accidental change visible in code review.

## Alternatives considered
- **Single base exception + central dispatch table** (`{DecodeError: 4, …}`) — rejected: splits the "what is this error?" knowledge into two places (the class and the table), making refactors error-prone.
- **Result tuples** (`(value, error_code) | (value, None)`, Go-style) — rejected: a 7-stage pipeline becomes deeply verbose with explicit propagation; Python idiom favours exceptions.
- **`SystemExit(code)` raised from stages** — rejected: bypasses our logging hook (the error line is emitted by the CLI catch, not the stage); also makes unit tests harder (tests have to catch `SystemExit` and inspect `.code`).

## Consequences
- **Positive:** mapping is centralized in the exception classes; CLI translation is one block of code; tests are type-based and stable. `mypy --strict` (`SRS.md` NFR-8) verifies the exception classes are used correctly.
- **Negative:** exit-code stability test must be kept up-to-date; if NFR-9 ever changes (a SemVer-major event per `SRS.md` Risk #8), the change ripples through both `errors.py` and the test. Acceptable cost.
- **Neutral:** the `event` class attr couples error logging to the exception hierarchy, which is fine because the catalogue is small (6 entries) and frozen as part of the v1.0.0 contract (`SRS.md` §16.1).

## Related
- ADR-0002 (Pipeline — raises these)
- ADR-0008 (Logging — consumes the `event` attr)
- `SRS.md` NFR-9, Risk #8, UC-1 E1–E9, AC-US-1.3/1.4/1.5, AC-US-5.4, AC-US-6.1, AC-US-6.4
- `SYSTEM_DESIGN.md` §3.2 (class diagram), §3.7 (mapping table)

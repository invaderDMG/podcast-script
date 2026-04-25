# ADR-0007: Module layout — flat `src/podcast_script/` package + `backends/` subpackage

- **Status:** Accepted
- **Date:** 2026-04-25
- **Deciders:** Solo maintainer
- **Supersedes:** —

## Context
The codebase has roughly ten modules (one per pipeline stage plus CLI/config/errors/logging/progress) and exactly two backend implementations (`faster-whisper`, `mlx-whisper`). `PROJECT_BRIEF.md` §5 chooses `hatchling` as the build backend, which conventionally pairs with the `src/`-layout (avoids accidental imports of the package from the working directory and is the layout `hatchling` documents first).

There is no plan for swappable IO (one filesystem source, one filesystem target), no domain-driven aggregate logic, and no plan for multiple deployable artifacts. The pipeline shape (decode → segment → transcribe → render) maps cleanly onto modules of the same names.

## Decision
Use a **flat `src/podcast_script/` package** with one module per stage / cross-cutting concern, plus a single `backends/` subpackage for the two Whisper implementations:

```
src/podcast_script/
    __init__.py          # version constant only; CLI is the public API
    __main__.py          # `python -m podcast_script` → cli.app()
    cli.py               # typer entrypoint, exit-code mapping, summary line
    config.py            # Config dataclass, TOML load + CLI merge, --lang validation
    errors.py            # PodcastScriptError + subclasses (ADR-0006)
    logging_setup.py     # logfmt Formatter, level routing (ADR-0008)
    progress.py          # rich Progress wrapper + non-TTY fallback
    pipeline.py          # Pipeline orchestrator (ADR-0002, ADR-0004, ADR-0005)
    decode.py            # ffmpeg subprocess wrapper
    segment.py           # inaSpeechSegmenter wrapper
    render.py            # pure Markdown renderer
    backends/
        __init__.py
        base.py          # WhisperBackend Protocol + select_backend() (ADR-0003)
        faster.py        # FasterWhisperBackend
        mlx.py           # MlxWhisperBackend
```

**Dependency direction (acyclic):**
- `cli` imports `config`, `pipeline`, `errors`, `logging_setup`.
- `pipeline` imports `decode`, `segment`, `render`, `progress`, `backends`, `errors`.
- `backends/{faster,mlx}` import `backends/base` only.
- `errors` and `logging_setup` are leaves (importable from anywhere).
- `__init__.py` does NOT import any submodule eagerly (keeps `--help` startup fast — see open Q8).

Tests live in `tests/{unit,integration,fixtures}/` outside the package.

## Alternatives considered
- **Layered subpackages** (`{cli, core, io, backends}/`) — rejected: imposes a layered-architecture vocabulary on a project that's actually a pipeline. Adds an import-path level (`from podcast_script.core.pipeline import …`) without buying separation we need.
- **Ports-and-adapters / hexagonal** — rejected: the pattern's value is swappable IO adapters; we have one filesystem source, one filesystem target. The ceremony (`domain/`, `application/`, `infrastructure/`) is unjustified at this size.
- **Flat package without a `backends/` subpackage** (just `backend_faster.py` + `backend_mlx.py` at the top level) — rejected: the two backends share enough (`base.py` Protocol, common error mapping) that a subpackage reads better; it's one extra directory level, not a cost.

## Consequences
- **Positive:** module names mirror the pipeline; new contributors find `decode.py` where they expect it; import paths stay short; `mypy --strict` runs cleanly without per-package config.
- **Negative:** if a stage grows beyond ~500 LOC and needs internal splitting (e.g. `segment.py` gets a separate model-loading helper), it'll either grow or sprout siblings (`segment_loader.py`) — not a subpackage. Acceptable trade-off for v1.
- **Neutral:** the `src/`-layout requires `pip install -e .` (or `uv sync`) to develop against; nobody runs `python -c "import podcast_script"` from a checkout without installing.

## Related
- ADR-0002 (Pipeline orchestrator — `pipeline.py`)
- ADR-0003 (WhisperBackend Protocol — `backends/base.py`)
- ADR-0006 (Error hierarchy — `errors.py`)
- `SRS.md` NFR-8 (lint/type-check/coverage discipline)
- `PROJECT_BRIEF.md` §5 (`hatchling`)
- `SYSTEM_DESIGN.md` §3.1

# ADR-0011: Lazy-import policy for heavy dependencies

- **Status:** Accepted
- **Date:** 2026-04-25
- **Deciders:** Solo maintainer
- **Supersedes:** —

## Context
Three of the runtime dependencies are heavy at import time:

- `inaSpeechSegmenter` pulls TensorFlow (~2–3 s cold import on a laptop, ~500 MB resident).
- `mlx-whisper` pulls MLX (Metal-bound; ~1 s import on Apple Silicon).
- `faster-whisper` pulls CTranslate2 (faster but still ~500 ms cold).

If any of these are imported at the top of a module reachable from `cli.py`, then `podcast-script --help`, `podcast-script --version`, and the validation-error paths (missing input, unsupported `--lang`, output already exists without `--force`) all pay the cold-import cost — turning a 50 ms operation into a 4 s one.

`SRS.md` Risk #5 also flags TensorFlow/MLX/CTranslate2 as a known combined-install hazard on macOS. Eager imports at module top mean an install conflict crashes startup before any useful error message can be emitted; lazy imports surface the failure at the first phase that genuinely needs the library, with full validation context already logged.

## Decision
**Heavy `import` statements live inside the stage class's `load()` method (or first-use site), never at module top.** Specifically:

- `segment.py` does not `import inaSpeechSegmenter` at module level. The import is inside `Segmenter.load()` (or whatever lazy-init method the class uses).
- `backends/faster.py` does not `import faster_whisper` at module level. The import is inside `FasterWhisperBackend.load()`.
- `backends/mlx.py` does not `import mlx_whisper` (or `mlx`) at module level. The import is inside `MlxWhisperBackend.load()`.
- `numpy` is acceptable at module top (lightweight, ubiquitous in the Python data ecosystem, ~150 ms cold).
- `__init__.py` does NOT import any of these submodules eagerly. It only exposes `__version__`.

`from __future__ import annotations` is used throughout the codebase so that *type annotations* referring to the heavy types (e.g. `np.ndarray`, library-specific result types) don't trigger imports either; type-checking-only imports go inside `if TYPE_CHECKING:` blocks.

This pattern keeps `--help` cold-start under 100 ms and makes any "TensorFlow + MLX install conflict" error appear at the segment phase with a useful traceback (the user has already seen `event=startup`, `event=config_loaded`, `event=backend_selected`, and the validation has passed).

## Alternatives considered
- **Eager top-of-module imports** — rejected: 4-second `--help`; install conflicts crash before validation; bad first-impression UX.
- **Lazy at `pipeline.py` only** (centralize the imports in the orchestrator) — rejected: `pipeline.py` is constructed in unit tests, which then drag in TF/MLX even when stages are mocked. Per-stage laziness is the right granularity.
- **Lazy via `importlib.import_module()` inside a helper** — rejected: equivalent to a plain `import` statement inside a function, but harder to read and not friendlier to mypy.

## Consequences
- **Positive:** `--help` stays snappy; validation errors appear within ~100 ms; install conflicts surface at the first phase that needs the library, with `event=…` context already logged. CI test fixtures that mock backends don't need TF or MLX installed.
- **Negative:** mypy needs `if TYPE_CHECKING: import …` patterns for any type annotations that reference library types — a small ergonomics cost. Library import failures inside `load()` propagate as unexpected `ImportError` (exit 1, not exit 5) unless we wrap them in `ModelError` explicitly. Mitigation: each stage's `load()` wraps its `import` block in `try / except ImportError as e: raise ModelError(...) from e` (see ADR-0006 for the typed-exception pattern).
- **Neutral:** import order across stages is implicit (whichever runs first triggers its imports); no global setup module needed.

## Related
- ADR-0002 (Pipeline orchestrator — drives `load()` order)
- ADR-0006 (typed exceptions — `ImportError` → `ModelError` wrap pattern)
- ADR-0007 (module layout — `__init__.py` minimalism)
- `SRS.md` Risk #5
- `SYSTEM_DESIGN.md` §3.1, §5 Risk #3

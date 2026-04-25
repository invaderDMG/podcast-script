# ADR-0003: WhisperBackend Protocol abstraction

- **Status:** Accepted
- **Date:** 2026-04-25
- **Deciders:** Solo maintainer
- **Supersedes:** —

## Context
`SRS.md` §1.2 commits to a hybrid Whisper backend: `faster-whisper` on Linux/CUDA/CPU, `mlx-whisper` on Apple Silicon, auto-selected by platform with a `--backend` override (also `SRS.md` F3, `PROJECT_BRIEF.md` §5–§6). The two libraries have different APIs, different model loading conventions, and different streaming behaviours, but the rest of the pipeline must not care which one is in use.

`SRS.md` Risk #1 explicitly flags two-backend complexity as a maintenance hazard and prescribes a thin abstraction. `SRS.md` §9.3 already mentions the abstraction informally ("the project may expose a `WhisperBackend` Protocol") but does not commit to its shape.

## Decision
Define a `WhisperBackend` **Protocol** (`typing.Protocol`, structural typing — no inheritance required) in `src/podcast_script/backends/base.py` with this minimal surface:

```python
class WhisperBackend(Protocol):
    name: str  # "faster-whisper" | "mlx-whisper"
    def load(self, model: str, device: str) -> None: ...
    def transcribe(
        self,
        pcm: np.ndarray,        # mono int16 or float32
        lang: str,              # one of the curated 8 (SRS §1.7)
        sample_rate: int = 16000,
    ) -> Iterable[TranscribedSegment]: ...
```

Two concrete implementations (`FasterWhisperBackend`, `MlxWhisperBackend`) live as siblings under `backends/`. A `select_backend(platform, backend_flag, device_flag) -> WhisperBackend` function (in `backends/base.py` or a sibling) handles the platform-detection rule (`arm64-darwin → mlx`, else `faster`) and validates `--backend mlx-whisper` only on Apple Silicon (`SRS.md` E7).

The Protocol is **internal**, not a stable public API for v1 (`SRS.md` §9.3). Its shape may change; users interact via the CLI.

## Alternatives considered
- **Abstract base class** (`abc.ABC`) — rejected: structural typing via Protocol is enough, doesn't force the third-party libraries' adapter classes to inherit from anything we own, and matches modern Python (3.12+) idiom.
- **No abstraction; conditional imports inside `pipeline.py`** — rejected: leaks library specifics into the orchestrator, makes unit-testing the pipeline impossible without installing both libraries.
- **Plugin/entry-point registry** (`importlib.metadata.entry_points`) — rejected: over-engineered for two known backends; revisit only if we ever support third-party backends out-of-tree.

## Consequences
- **Positive:** `Pipeline` depends only on the Protocol; tests pass a fake `WhisperBackend` implementation that returns canned `TranscribedSegment` lists without touching any real model. CI can run unit tests without `faster-whisper` or `mlx-whisper` installed.
- **Negative:** the Protocol's `transcribe` signature has to be the lowest common denominator of both libraries; any backend-specific tuning (e.g. `faster-whisper`'s `vad_filter`, `mlx-whisper`'s `word_timestamps`) is hidden inside the implementation, not exposed via flags.
- **Neutral:** Protocols are duck-typed at the call site; static checking via `mypy --strict` (`SRS.md` NFR-8) is fine because we annotate concrete classes against the Protocol explicitly in tests.

## Related
- ADR-0002 (Pipeline orchestrator — the consumer of this Protocol)
- ADR-0004 (Streaming transcribe — what `Iterable[TranscribedSegment]` enables)
- `SRS.md` F3, §9.3, Risk #1, E7
- `PROJECT_BRIEF.md` §5–§6
- `SYSTEM_DESIGN.md` §2.3 (C-FasterWhisper / C-MlxWhisper), §3.2, §3.4

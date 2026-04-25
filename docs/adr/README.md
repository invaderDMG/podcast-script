# Architecture Decision Records

ADRs for `podcast-script`. Format: Michael Nygard (per ADR-0001). Each ADR is **immutable once accepted**; if a decision changes, a new ADR supersedes it (the old one stays on disk with `Status: Superseded by NNNN`). Numbering is monotonic and never reused.

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [0001](0001-adr-format-nygard.md) | ADR format — Michael Nygard | Accepted | 2026-04-25 |
| [0002](0002-pipes-and-filters-pipeline.md) | Architectural style — pipes-and-filters pipeline with explicit orchestrator class | Accepted | 2026-04-25 |
| [0003](0003-whisper-backend-protocol.md) | WhisperBackend Protocol abstraction | Accepted | 2026-04-25 |
| [0004](0004-streaming-per-segment-transcribe.md) | Streaming per-speech-segment transcribe for bounded peak RSS | Accepted | 2026-04-25 |
| [0005](0005-atomic-output-via-temp-and-rename.md) | Atomic output via temp file + rename | Accepted | 2026-04-25 |
| [0006](0006-error-to-exit-code-via-typed-exceptions.md) | Error → exit-code mapping via typed exception hierarchy | Accepted | 2026-04-25 |
| [0007](0007-flat-src-package-layout.md) | Module layout — flat `src/podcast_script/` package + `backends/` subpackage | Accepted | 2026-04-25 |
| [0008](0008-rich-progress-and-logfmt-coexistence.md) | Coexisting `rich` progress + logfmt logs on stderr via `Progress.console` | Accepted | 2026-04-25 |
| [0009](0009-backend-load-ordering.md) | Backend `load()` ordering — eager, before decode | Accepted | 2026-04-25 |
| [0010](0010-pipeline-level-progress-tick.md) | Transcribe progress tick granularity — pipeline-level, per speech segment | Accepted | 2026-04-25 |
| [0011](0011-lazy-imports-for-heavy-deps.md) | Lazy-import policy for heavy dependencies | Accepted | 2026-04-25 |
| [0012](0012-event-catalogue-freeze.md) | Event catalogue freeze for v1.0.0 | Accepted | 2026-04-25 |
| [0013](0013-config-stdlib-tomllib-dataclass.md) | Config implementation — stdlib `tomllib` + `dataclasses.dataclass` | Accepted | 2026-04-25 |
| [0014](0014-sigint-keyboardinterrupt-handling.md) | SIGINT / KeyboardInterrupt handling | Accepted | 2026-04-25 |
| [0015](0015-debug-dir-pre-existence-policy.md) | `--debug` artifact directory pre-existence policy | Accepted | 2026-04-25 |
| [0016](0016-pcm-float32-mono-16khz.md) | Decoded PCM format — `float32` mono 16 kHz | Accepted | 2026-04-25 |
| [0017](0017-three-tier-test-strategy.md) | Three-tier test strategy — unit / contract / integration | Accepted | 2026-04-25 |

# ADR-0010: Transcribe progress tick granularity — pipeline-level, per speech segment

- **Status:** Accepted
- **Date:** 2026-04-25
- **Deciders:** Solo maintainer
- **Supersedes:** —

## Context
`SRS.md` AC-US-3.1 requires the transcribe progress task to update "per segment during transcribe", giving the user a sense of progress on long episodes. There are two candidate sources of "segments" to tick on:

1. **Speech segments from the segmenter** (the outer loop in ADR-0004) — known total upfront after the segmenter pass; stable across both backends.
2. **`TranscribedSegment` yields from the backend** (Whisper's internal windowing) — natural and smooth from `faster-whisper`, but `mlx-whisper`'s API is more whole-file-oriented and may yield all results at once at the end of a `.transcribe()` call (`SYSTEM_DESIGN.md` §5 Risk #4).

If we tick per backend yield, the progress UX diverges across platforms — Linux users see a smooth bar, Apple Silicon users see a jump from 0% to 100% at the end of each speech segment.

## Decision
Tick the transcribe progress task at the **pipeline level, once per outer-loop iteration over speech segments**. The total is set to `len(speech_segments)` after the segmenter pass.

```python
# pipeline.py (sketch)
speech_segments = [s for s in all_segments if s.label == "speech"]
transcribe_task = progress.add_task("transcribe", total=len(speech_segments))
for seg in speech_segments:
    pcm_slice = pcm[int(seg.start * sr):int(seg.end * sr)]
    for ts in backend.transcribe(pcm_slice, lang):
        renderer.feed_speech(seg.start + ts.start, ts.text)
    progress.advance(transcribe_task, 1)  # tick once per outer iteration
```

This is **backend-agnostic**: whether `mlx-whisper` yields incrementally or returns its full list at the end of `.transcribe()`, the progress bar still ticks once per speech segment with the same UX on every platform.

## Alternatives considered
- **Backend-yield-driven** (one tick per `TranscribedSegment` produced) — rejected: smooth on `faster-whisper`, broken on `mlx-whisper`; cross-platform UX divergence violates the spirit of NFR-7 (runs unchanged across OSes).
- **Time-based ETA** (tick by elapsed wall-clock vs. estimated total = `audio_duration × known_RTF_per_backend`) — rejected: real-time-factor varies wildly with hardware and model size; an ETA model that misleads is worse than ticks-per-segment.
- **Tick per byte of decoded PCM consumed** (manual cursor over the array) — rejected: fine-grained but requires re-implementing the per-segment slicing accounting; no real benefit over per-speech-segment.

## Consequences
- **Positive:** identical progress UX on Linux/CUDA, Linux/CPU, and Apple Silicon; total is known upfront so the bar's percentage is meaningful; sidesteps Risk #4 entirely.
- **Negative:** a single very-long speech segment (e.g. an uninterrupted 10-minute monologue) shows zero in-segment progress. In practice `inaSpeechSegmenter` chops speech into ≤ 1-minute regions on typical podcasts, so this is rarely visible; documented as a minor caveat in the README's "what to expect" section.
- **Neutral:** the renderer still receives `TranscribedSegment`s as they arrive within each backend call, so memory boundedness (ADR-0004) is unaffected.

## Related
- ADR-0002 (Pipeline orchestrator — owns the loop)
- ADR-0003 (WhisperBackend Protocol — `Iterable[TranscribedSegment]`)
- ADR-0004 (Streaming per-segment transcribe — outer loop shape)
- `SRS.md` AC-US-3.1, NFR-2, NFR-7
- `SYSTEM_DESIGN.md` §3.5 SD-UC-1 (tick site), §5 Risk #4

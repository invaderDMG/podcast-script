# ADR-0004: Streaming per-speech-segment transcribe for bounded peak RSS

- **Status:** Accepted
- **Date:** 2026-04-25
- **Deciders:** Solo maintainer
- **Supersedes:** —

## Context
`SRS.md` NFR-2 requires that peak resident-set memory MUST NOT be a function of episode length, motivated by EC-4 (≥ 3 hour episodes). The transcribe phase is the dominant memory consumer (Whisper internals + accumulated transcribed text). The segmenter phase already produces a list of speech regions ahead of transcribe, so the transcribe phase has a natural unit-of-work: one speech segment.

Two contracts collide here:

1. **Memory:** if the pipeline waits to accumulate every transcribed segment in memory before rendering, memory grows linearly with episode length.
2. **Progress UX:** `SRS.md` AC-US-3.1 requires per-segment progress ticks during transcribe — the bar must reflect work-in-progress, not jump from 0% to 100% at the end.

The segmenter output itself (the list of `(start, end, label)` triples) is small (a few KB even for multi-hour episodes) and is held end-to-end. The decoded PCM is also held end-to-end (`SYSTEM_DESIGN.md` §2.4 — ~110 MB/h, acceptable). The variable cost is the transcribed-text accumulation.

## Decision
The `Pipeline` orchestrator iterates speech segments one-at-a-time:

```python
for seg in speech_segments:
    pcm_slice = pcm[int(seg.start * sr):int(seg.end * sr)]
    for transcribed in backend.transcribe(pcm_slice, lang):
        renderer.feed_speech(seg.start + transcribed.start, transcribed.text)
        progress.tick(transcribe_task)
```

The renderer accepts incremental input (`feed_speech` / `feed_music_marker`) and accumulates only the *output Markdown lines* (which are short text, bounded by transcript length — a 3 h Spanish podcast Markdown file is well under 10 MB). It does NOT accumulate raw `TranscribedSegment` objects with their floats and metadata.

The backend's `transcribe()` returns an `Iterable[TranscribedSegment]`, allowing each implementation to yield as soon as the underlying library has output (`faster-whisper` does this naturally; `mlx-whisper` may need internal buffering — see open Q7).

## Alternatives considered
- **Whole-file transcribe** (call `backend.transcribe(full_pcm, lang)` once, get back the full list, render after) — rejected: trivial to implement, fails NFR-2 for multi-hour episodes, and progress jumps from 0 to 100%.
- **Streaming PCM too** (chunked ffmpeg pipe → segmenter on chunks → transcribe on chunks) — rejected for v1: segmentation needs whole-file context to avoid splitting music regions across chunk boundaries; cost (multiple seconds of design + correctness work) exceeds benefit (saving ~100 MB on a 3 h episode that already fits comfortably in RAM).
- **Out-of-process worker** for the transcribe loop — rejected: adds IPC complexity; we have no concurrency requirement.

## Consequences
- **Positive:** peak RSS for the transcribe phase is bounded to one segment's audio + one segment's transcribed text + the model weights, regardless of episode length. NFR-2 holds. Progress bar ticks per segment.
- **Negative:** more loop overhead per call; not a bottleneck in practice (Whisper inference dwarfs Python loop cost). `mlx-whisper` may not stream as cleanly as `faster-whisper` (Risk #4 in `SYSTEM_DESIGN.md` §5; addressed in a separate ADR after Q7 lands).
- **Neutral:** the renderer's `feed_*` API is internal; no public contract.

## Related
- ADR-0002 (Pipeline orchestrator — drives this loop)
- ADR-0003 (WhisperBackend Protocol — the streaming contract)
- `SRS.md` NFR-2, EC-4, AC-US-3.1
- `SYSTEM_DESIGN.md` §2.4, §3.5 SD-UC-1, §5 Risk #4 / #5

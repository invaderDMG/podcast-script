# ADR-0016: Decoded PCM format — `float32` mono 16 kHz

- **Status:** Accepted
- **Date:** 2026-04-25
- **Deciders:** Solo maintainer
- **Supersedes:** —

## Context
The decoder (C-Decode, `decode.py`) produces a single in-memory PCM buffer that is then consumed by:

1. The segmenter (`inaSpeechSegmenter`) for music/speech labelling.
2. The Whisper backend (`faster-whisper` or `mlx-whisper`) for transcription.

All three downstream consumers ultimately want **mono 16 kHz** audio (`PROJECT_BRIEF.md` §6 and Whisper convention). The remaining choice is the sample dtype: `float32` (32 bits/sample, normalized to ±1.0) or `int16` (16 bits/sample, signed integer).

Survey of expectations:
- `inaSpeechSegmenter` accepts `float32` directly via its `Segmenter`-on-PCM API; it accepts WAV files too but PCM in-memory needs `float32`.
- `faster-whisper` accepts `np.ndarray[np.float32]`; `int16` requires manual normalization (`pcm.astype(np.float32) / 32768.0`).
- `mlx-whisper` accepts `np.ndarray[np.float32]` (MLX tensors are converted internally).

`SRS.md` NFR-2 says peak RSS must not be a function of episode length; reading "function of" literally allows a constant proportion (~110 MB/h for `int16`, ~220 MB/h for `float32` at mono/16 kHz). On a 3-hour episode (EC-4 worst case), that's ~660 MB of PCM in `float32` vs. ~330 MB in `int16` — both fit comfortably in the target hardware (the maintainer's Apple Silicon laptop and Ubuntu CI runners have ≥ 8 GB RAM minimum).

## Decision
Decode to **`float32` mono 16 kHz** in-memory. The ffmpeg invocation is:

```
ffmpeg -i <input> -f f32le -ar 16000 -ac 1 -hide_banner -loglevel error -
```

(`-f f32le` = raw float32 little-endian; `-ar 16000` = 16 kHz; `-ac 1` = mono; `-` = stdout). The output is read into a `np.frombuffer(stdout, dtype=np.float32)` in C-Decode and passed unchanged to both downstream consumers.

Under `--debug`, `decoded.wav` is written separately via a `wave` or `soundfile` write of the same buffer (in WAV's standard `int16` for compatibility — `decoded.wav` is for human inspection in audio tools that may not understand raw `f32le`).

## Alternatives considered
- **`int16` mono 16 kHz** — half the memory footprint and ffmpeg-native, but requires per-backend normalization (`pcm.astype(np.float32) / 32768.0`) before passing to Whisper. The conversion is mechanical but introduces dtype-handling code that's easy to get wrong (off-by-one normalizer, signedness drift) and adds an extra full-buffer pass per backend call, which fights NFR-2.
- **Library-dependent format per stage** — rejected: would require either re-decoding per stage or maintaining a separate per-stage buffer. Re-decoding violates "decode once, segment once, transcribe once" and bloats wall time on long inputs; per-stage buffers explode memory.
- **`float64` mono 16 kHz** — rejected: doubles memory again over `float32` for no quality benefit (Whisper internals are `float32` or below); pure waste.

## Consequences
- **Positive:** one decoded buffer feeds both consumers without conversion. Code path is straight-line: `ffmpeg → np.frombuffer → seg.segment(pcm) → for each speech: backend.transcribe(pcm[a:b])`. No dtype-handling subtlety in stage code. Matches every library's "happy path" input.
- **Negative:** ~220 MB/h peak RSS during transcribe on long episodes vs. ~110 MB/h for `int16`. Acceptable per NFR-2 reading; revisit if real-world reports surface OOM on memory-constrained hardware (Risk #5 in `SYSTEM_DESIGN.md` §5).
- **Neutral:** the `decoded.wav` debug artifact is `int16` (WAV convention) rather than the in-memory `float32`; users opening it in Audacity / Reaper see normal-looking audio.

## Related
- ADR-0002 (Pipeline orchestrator — owns the buffer)
- ADR-0003 (WhisperBackend Protocol — `pcm: np.ndarray` parameter typing)
- ADR-0004 (streaming transcribe — slices the same buffer)
- `SRS.md` NFR-2, EC-4, AC-US-7.1 (`decoded.wav` shape)
- `SYSTEM_DESIGN.md` §2.3 C-Decode, §5 Risk #5

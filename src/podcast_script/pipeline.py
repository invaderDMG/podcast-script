"""Pipeline orchestrator (POD-008).

Pipes-and-filters orchestrator (ADR-0002) running the canonical SP-1/SP-2
sequence: ``backend.load`` → ``decode`` → fmt-by-duration → ``segment`` →
streaming per-speech-segment ``transcribe`` (ADR-0004) → ``render`` →
atomic ``os.replace`` (ADR-0005).

Backend ``load`` runs eagerly *before* decode (ADR-0009) so the AC-US-5.1
first-run download notice fires inside the NFR-6 1 s budget regardless of
episode length. Stages arrive via constructor injection (Tier 1 unit
tests inject fakes; the cli wires the real stages in
:func:`podcast_script.cli._run_pipeline`).

The pipeline never calls ``sys.exit`` — it raises the typed
:class:`~podcast_script.errors.PodcastScriptError` subclasses, and
:mod:`podcast_script.cli` alone translates them to exit codes per
ADR-0006. Phase-boundary events are emitted from the ``podcast_script``
logger tree per the ADR-0012 catalogue (the regex-level enforcement of
that catalogue lands in POD-033 / POD-015).
"""

from __future__ import annotations

import json
import logging
import time
import wave
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt

from .atomic_write import atomic_write
from .backends.base import TranscribedSegment, WhisperBackend
from .progress import DECODE_TASK, SEGMENT_TASK, TRANSCRIBE_TASK, Progress
from .render import RenderFn, TimestampFormat
from .segment import Segment, Segmenter, to_jsonl

DecodeFn = Callable[[Path], npt.NDArray[np.float32]]
"""Callable signature the cli supplies to bind ``debug_dir`` and friends
without leaking those concerns into the orchestrator (ADR-0002 §Decision
step 4 — stages injected for testability)."""

_ONE_HOUR_S = 3600
"""Threshold for AC-US-2.4 ``MM:SS`` vs. ``HH:MM:SS`` selection. The
Pipeline owns the choice (ADR-0002 §Context); the renderer applies it."""

_log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RunSummary:
    """Data the cli needs after a successful run to emit ``event=done``.

    Per SRS UC-1 step 10 / ADR-0012 the locked summary line carries
    ``input``, ``output``, ``backend``, ``model``, ``lang``,
    ``duration_in_s`` and ``duration_wall_s``. The cli already knows
    every other field; only ``duration_in_s`` (the audio duration the
    decoder measured) is computed inside the pipeline. Returning it as
    a small frozen dataclass keeps the surface honest about who owns
    which key without smuggling state through a global.
    """

    duration_in_s: float


@dataclass
class Pipeline:
    """Orchestrates one transcribe run.

    Stages are injected so unit tests can substitute fakes (ADR-0017
    Tier 1). The class deliberately holds no state across runs — one
    :class:`Pipeline` may be re-used, but each :meth:`run` is independent.
    """

    decode: DecodeFn
    segmenter: Segmenter
    backend: WhisperBackend
    render: RenderFn
    model: str
    device: str
    lang: str
    sample_rate: int = 16_000
    # POD-013 — optional progress bar. When ``None`` the pipeline runs
    # silently (Tier 1 unit-test path); when present, the cli composition
    # root has wired :func:`podcast_script.progress.make_progress` and the
    # phase methods tick it per ADR-0010.
    progress: Progress | None = None
    # POD-024 — optional ``<input-stem>.debug/`` artifact directory.
    # When set, each phase persists its output (decoded.wav / segments
    # .jsonl / transcribe.jsonl); ``decode()`` writes commands.txt
    # itself when the cli passes ``debug_dir`` through the partial.
    # Default ``None`` = no artifacts (AC-US-7.2).
    debug_dir: Path | None = None

    def run(self, *, input_path: Path, output_path: Path) -> RunSummary:
        """Run the full pipeline; write Markdown atomically to ``output_path``.

        Returns a :class:`RunSummary` carrying ``duration_in_s`` for the
        cli's ``event=done`` summary (UC-1 step 10). Raises
        :class:`~podcast_script.errors.PodcastScriptError` subclasses on
        stage failures (the cli translates these to exit codes). On any
        failure before :func:`atomic_write` succeeds, ``output_path`` is
        guaranteed untouched per ADR-0005.
        """
        self._load_backend()
        pcm = self._decode(input_path)
        fmt = self._choose_fmt(pcm)
        segments = self._segment(pcm)
        transcripts = self._transcribe_speech(pcm, segments)
        markdown = self._render(segments, transcripts, fmt)
        self._write(output_path, markdown)
        return RunSummary(duration_in_s=len(pcm) / self.sample_rate)

    def _load_backend(self) -> None:
        """ADR-0009: eager ``backend.load`` before decode."""
        _log.info(
            "",
            extra={
                "event": "model_load_start",
                "backend": self.backend.name,
                "model": self.model,
                "device": self.device,
            },
        )
        wall_start = time.monotonic()
        self.backend.load(self.model, self.device)
        _log.info(
            "",
            extra={
                "event": "model_load_done",
                "backend": self.backend.name,
                "model": self.model,
                "device": self.device,
                "duration_wall_s": f"{time.monotonic() - wall_start:.3f}",
            },
        )

    def _decode(self, input_path: Path) -> npt.NDArray[np.float32]:
        """Call the injected decode function; emit phase events.

        The decode callable raises typed exceptions (``InputIOError``,
        ``DecodeError``, ``UsageError``); the pipeline lets them propagate
        — ADR-0006 keeps the exit-code translation in cli.
        """
        _log.info("", extra={"event": "decode_start", "input": str(input_path)})
        pcm = self.decode(input_path)
        duration_s = len(pcm) / self.sample_rate
        _log.info(
            "",
            extra={
                "event": "decode_done",
                "duration_in_s": f"{duration_s:.3f}",
            },
        )
        if self.progress is not None:
            self.progress.advance(DECODE_TASK, 1)
        if self.debug_dir is not None:
            self._write_decoded_wav(pcm)
        return pcm

    def _choose_fmt(self, pcm: npt.NDArray[np.float32]) -> TimestampFormat:
        """AC-US-2.4: ``MM:SS`` for inputs < 1 h, ``HH:MM:SS`` for ≥ 1 h."""
        duration_s = len(pcm) / self.sample_rate
        return "HH:MM:SS" if duration_s >= _ONE_HOUR_S else "MM:SS"

    def _segment(self, pcm: npt.NDArray[np.float32]) -> list[Segment]:
        _log.info("", extra={"event": "segment_start"})
        segments = self.segmenter.segment(pcm)
        _log.info(
            "",
            extra={"event": "segment_done", "n_segments": len(segments)},
        )
        if self.progress is not None:
            self.progress.advance(SEGMENT_TASK, 1)
            # ADR-0010 — set the transcribe task's total now that we know
            # how many speech segments will be processed; the bar's
            # percentage becomes meaningful for the transcribe phase.
            n_speech = sum(1 for s in segments if s.label == "speech")
            self.progress.update(TRANSCRIBE_TASK, total=n_speech)
        if self.debug_dir is not None:
            self._write_segments_jsonl(segments)
        return segments

    def _transcribe_speech(
        self,
        pcm: npt.NDArray[np.float32],
        segments: list[Segment],
    ) -> list[TranscribedSegment]:
        """ADR-0004 streaming contract: one ``transcribe`` call per speech
        segment. Re-anchors backend offsets (relative to slice start) onto
        absolute episode time before handing to the renderer.
        """
        speech_segments = [s for s in segments if s.label == "speech"]
        _log.info(
            "",
            extra={
                "event": "transcribe_start",
                "n_speech_segments": len(speech_segments),
            },
        )
        transcripts: list[TranscribedSegment] = []
        for seg in speech_segments:
            start_idx = int(seg.start * self.sample_rate)
            end_idx = int(seg.end * self.sample_rate)
            for ts in self.backend.transcribe(pcm[start_idx:end_idx], self.lang, self.sample_rate):
                transcripts.append(
                    TranscribedSegment(
                        start=seg.start + ts.start,
                        end=seg.start + ts.end,
                        text=ts.text,
                    )
                )
            # ADR-0010 — tick once per outer-loop iteration over speech
            # segments. Backend-agnostic: faster-whisper yields incrementally
            # while mlx-whisper may yield all results at once at the end of
            # ``transcribe()``. The user sees the same UX on both.
            if self.progress is not None:
                self.progress.advance(TRANSCRIBE_TASK, 1)
        _log.info(
            "",
            extra={
                "event": "transcribe_done",
                "n_speech_segments": len(speech_segments),
            },
        )
        if self.debug_dir is not None:
            self._write_transcribe_jsonl(transcripts)
        return transcripts

    def _render(
        self,
        segments: list[Segment],
        transcripts: list[TranscribedSegment],
        fmt: TimestampFormat,
    ) -> str:
        markdown = self.render(segments, transcripts, fmt)
        _log.info("", extra={"event": "render_done"})
        return markdown

    def _write(self, output_path: Path, markdown: str) -> None:
        """Atomic temp+rename via :func:`atomic_write` (ADR-0005)."""
        atomic_write(output_path, markdown)
        _log.info("", extra={"event": "write_done", "output": str(output_path)})

    # ------------------------------------------------------------------
    # POD-024 — --debug artifact writes (AC-US-7.1)
    # ------------------------------------------------------------------

    def _write_decoded_wav(self, pcm: npt.NDArray[np.float32]) -> None:
        """Persist ``decoded.wav`` (mono 16 kHz int16) to the debug dir.

        ``decode()`` returns float32 PCM in [-1.0, 1.0] per ADR-0016;
        we clip and scale to int16 for the WAV header convention. The
        directory is created lazily so the cli doesn't have to mkdir
        before the run starts. ADR-0013 forbids new runtime deps, so
        we use stdlib :mod:`wave` (no soundfile / scipy).
        """
        assert self.debug_dir is not None  # narrowed by callers
        self.debug_dir.mkdir(parents=True, exist_ok=True)

        clipped = np.clip(pcm, -1.0, 1.0)
        int16 = (clipped * 32767.0).astype(np.int16)
        with wave.open(str(self.debug_dir / "decoded.wav"), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.sample_rate)
            w.writeframes(int16.tobytes())

    def _write_segments_jsonl(self, segments: list[Segment]) -> None:
        """Persist ``segments.jsonl`` (one JSON object per segment).

        Format locked by AC-US-7.1: ``{start, end, label}``; reuses
        :func:`podcast_script.segment.to_jsonl` so the segments-side
        canonical wire format lives in one place.
        """
        assert self.debug_dir is not None
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        (self.debug_dir / "segments.jsonl").write_text(to_jsonl(segments), encoding="utf-8")

    def _write_transcribe_jsonl(self, transcripts: list[TranscribedSegment]) -> None:
        """Persist ``transcribe.jsonl`` (one JSON object per
        re-anchored transcription).

        Format locked by AC-US-7.1: ``{start, end, text}``. ``start``
        / ``end`` are absolute episode time (the pipeline already
        re-anchors offsets in :meth:`_transcribe_speech`).
        """
        assert self.debug_dir is not None
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        lines = [
            json.dumps({"start": ts.start, "end": ts.end, "text": ts.text}) for ts in transcripts
        ]
        body = "\n".join(lines) + "\n" if lines else ""
        (self.debug_dir / "transcribe.jsonl").write_text(body, encoding="utf-8")

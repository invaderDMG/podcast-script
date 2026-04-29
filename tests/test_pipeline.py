"""Tests for the Pipeline orchestrator (POD-008).

Tier 1 unit tests per ADR-0017: pure orchestration logic exercised against
fake stages (``FakeBackend``, ``FakeSegmenter``, ``fake_render``) — no
heavy ML deps imported, suite stays under the ≤ 1 s budget. The
real-stage integration tests live in Tier 3 (POD-031, SP-7).

The fakes implement the Protocols declared in
:mod:`podcast_script.backends.base`, :mod:`podcast_script.segment`, and
:mod:`podcast_script.render` to make sure the orchestrator depends only
on the contracts, not on the concrete stages POD-010 / POD-011 / POD-019
will land later.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import numpy as np
import numpy.typing as npt
import pytest

from podcast_script.backends.base import TranscribedSegment
from podcast_script.errors import DecodeError, InputIOError
from podcast_script.pipeline import Pipeline
from podcast_script.render import TimestampFormat
from podcast_script.segment import Segment

SAMPLE_RATE = 16_000


def _silence_pcm(duration_s: float) -> npt.NDArray[np.float32]:
    """Return a zeroed float32 PCM array of ``duration_s`` seconds at 16 kHz."""
    return np.zeros(int(duration_s * SAMPLE_RATE), dtype=np.float32)


class _FakeBackend:
    """In-memory ``WhisperBackend`` that records every call.

    The real ``faster-whisper`` / ``mlx-whisper`` backends arrive in
    POD-019 / POD-020. Until then this fake exercises the orchestrator
    against the Protocol surface declared in :mod:`backends.base`.
    """

    name = "fake"

    def __init__(self, *, transcripts_per_call: list[TranscribedSegment] | None = None) -> None:
        self.load_calls: list[tuple[str, str]] = []
        self.transcribe_calls: list[tuple[int, str, int]] = []  # (pcm_len, lang, sample_rate)
        self._canned = transcripts_per_call or [TranscribedSegment(0.0, 1.0, "hola")]

    def load(self, model: str, device: str) -> None:
        self.load_calls.append((model, device))

    def transcribe(
        self,
        pcm: npt.NDArray[np.float32],
        lang: str,
        sample_rate: int = SAMPLE_RATE,
    ) -> Iterable[TranscribedSegment]:
        self.transcribe_calls.append((len(pcm), lang, sample_rate))
        return list(self._canned)


class _FakeSegmenter:
    """In-memory ``Segmenter`` that returns canned :class:`Segment` lists."""

    def __init__(self, segments: list[Segment]) -> None:
        self._segments = segments
        self.calls: list[int] = []  # pcm length per call

    def segment(self, pcm: npt.NDArray[np.float32]) -> list[Segment]:
        self.calls.append(len(pcm))
        return list(self._segments)


def _stub_render(
    segments: list[Segment],
    transcripts: list[TranscribedSegment],
    fmt: TimestampFormat,
) -> str:
    """Tiny renderer: enough markdown to verify content lands intact."""
    lines = [f"# transcript ({fmt})"]
    for ts in transcripts:
        lines.append(f"- [{ts.start:.2f}-{ts.end:.2f}] {ts.text}")
    return "\n".join(lines) + "\n"


def _make_pipeline(
    *,
    pcm: npt.NDArray[np.float32],
    segments: list[Segment],
    transcripts_per_call: list[TranscribedSegment] | None = None,
    decode_error: Exception | None = None,
) -> tuple[Pipeline, _FakeBackend, _FakeSegmenter]:
    """Construct a Pipeline wired with fakes for unit-level testing."""
    backend = _FakeBackend(transcripts_per_call=transcripts_per_call)
    segmenter = _FakeSegmenter(segments)

    def decode(_input_path: Path) -> npt.NDArray[np.float32]:
        if decode_error is not None:
            raise decode_error
        return pcm

    pipeline = Pipeline(
        decode=decode,
        segmenter=segmenter,
        backend=backend,
        render=_stub_render,
        model="tiny",
        device="cpu",
        lang="es",
        sample_rate=SAMPLE_RATE,
    )
    return pipeline, backend, segmenter


def test_pipeline_writes_to_resolved_output_path_AC_US_1_1(tmp_path: Path) -> None:
    """AC-US-1.1 (orchestrator boundary): the resolved output Markdown lands.

    The default-path *resolution* (``input_path.with_suffix(".md")``) lives
    in :mod:`podcast_script.cli`, not in :class:`Pipeline`; this test
    verifies the orchestrator writes to whichever path the cli passed in
    — i.e. the cli/Pipeline contract for AC-US-1.1.
    """
    input_path = tmp_path / "episode.mp3"
    input_path.write_bytes(b"")  # decode is faked; existence keeps cli-wiring honest
    output_path = tmp_path / "episode.md"

    pipeline, _backend, _segmenter = _make_pipeline(
        pcm=_silence_pcm(2.0),
        segments=[Segment(0.0, 2.0, "speech")],
    )
    pipeline.run(input_path=input_path, output_path=output_path)

    assert output_path.is_file()
    body = output_path.read_text(encoding="utf-8")
    assert body.startswith("# transcript (MM:SS)")
    assert "hola" in body


def test_pipeline_writes_explicit_output_AC_US_1_2(tmp_path: Path) -> None:
    """AC-US-1.2: with ``-o`` set, output lands exactly at the explicit path."""
    input_path = tmp_path / "episode.mp3"
    input_path.write_bytes(b"")
    explicit_output = tmp_path / "elsewhere" / "custom.md"
    explicit_output.parent.mkdir()

    pipeline, _backend, _segmenter = _make_pipeline(
        pcm=_silence_pcm(2.0),
        segments=[Segment(0.0, 2.0, "speech")],
    )
    pipeline.run(input_path=input_path, output_path=explicit_output)

    assert explicit_output.is_file()
    # The default sibling path MUST NOT be created.
    assert not (tmp_path / "episode.md").exists()


def test_pipeline_decode_error_no_output_AC_US_1_3(tmp_path: Path) -> None:
    """AC-US-1.3: ``ffmpeg`` failure raises ``DecodeError``; no output, no temp."""
    input_path = tmp_path / "broken.mp3"
    input_path.write_bytes(b"")
    output_path = tmp_path / "broken.md"

    pipeline, _backend, _segmenter = _make_pipeline(
        pcm=_silence_pcm(0.0),  # unused — decode raises first
        segments=[],
        decode_error=DecodeError("ffmpeg failed (exit 1) decoding broken.mp3: bad header"),
    )
    with pytest.raises(DecodeError):
        pipeline.run(input_path=input_path, output_path=output_path)

    assert not output_path.exists()
    # No half-file: no leftover temp from atomic_write
    assert not list(tmp_path.glob("*.md.tmp*"))


def test_pipeline_input_io_error_no_output_AC_US_1_4(tmp_path: Path) -> None:
    """AC-US-1.4: missing/unreadable input raises ``InputIOError``; no output."""
    input_path = tmp_path / "missing.mp3"  # deliberately not created
    output_path = tmp_path / "missing.md"

    pipeline, _backend, _segmenter = _make_pipeline(
        pcm=_silence_pcm(0.0),
        segments=[],
        decode_error=InputIOError(f"input file not found: {input_path}"),
    )
    with pytest.raises(InputIOError):
        pipeline.run(input_path=input_path, output_path=output_path)

    assert not output_path.exists()


def test_backend_loaded_eagerly_before_decode_ADR_0009(tmp_path: Path) -> None:
    """ADR-0009: ``backend.load()`` MUST run before decode.

    Verified by injecting a ``DecodeError`` and asserting ``load`` was
    still recorded — i.e. the eager-load happens before decode raises, so
    the AC-US-5.1 first-run download notice fires inside the 1 s NFR-6
    budget regardless of episode length.
    """
    input_path = tmp_path / "episode.mp3"
    input_path.write_bytes(b"")
    output_path = tmp_path / "episode.md"

    pipeline, backend, _segmenter = _make_pipeline(
        pcm=_silence_pcm(0.0),
        segments=[],
        decode_error=DecodeError("simulated"),
    )
    with pytest.raises(DecodeError):
        pipeline.run(input_path=input_path, output_path=output_path)

    assert backend.load_calls == [("tiny", "cpu")]


def test_transcribe_called_per_speech_segment_ADR_0004(tmp_path: Path) -> None:
    """ADR-0004: streaming contract — one ``transcribe`` call per speech segment.

    A 6-second PCM with three labeled regions (speech / music / speech)
    must result in exactly two transcribe calls, each receiving its
    segment's PCM slice (not the whole array).
    """
    input_path = tmp_path / "episode.mp3"
    input_path.write_bytes(b"")
    output_path = tmp_path / "episode.md"

    segments = [
        Segment(0.0, 2.0, "speech"),
        Segment(2.0, 4.0, "music"),
        Segment(4.0, 6.0, "speech"),
    ]
    pipeline, backend, _segmenter = _make_pipeline(
        pcm=_silence_pcm(6.0),
        segments=segments,
    )
    pipeline.run(input_path=input_path, output_path=output_path)

    pcm_lens = [call[0] for call in backend.transcribe_calls]
    assert pcm_lens == [2 * SAMPLE_RATE, 2 * SAMPLE_RATE]


def test_pipeline_skips_noise_and_silence_segments_ADR_0004(tmp_path: Path) -> None:
    """``noise`` / ``silence`` segments MUST NOT be sent to ``backend.transcribe``.

    Companion to AC-US-2.5 / NFR-4: keeping these out of the transcribe
    loop is what bounds inference cost on noisy episodes; the renderer
    drops their *output lines* separately in POD-011.
    """
    input_path = tmp_path / "episode.mp3"
    input_path.write_bytes(b"")
    output_path = tmp_path / "episode.md"

    segments = [
        Segment(0.0, 1.0, "silence"),
        Segment(1.0, 3.0, "speech"),
        Segment(3.0, 4.0, "noise"),
    ]
    pipeline, backend, _segmenter = _make_pipeline(
        pcm=_silence_pcm(4.0),
        segments=segments,
    )
    pipeline.run(input_path=input_path, output_path=output_path)

    assert len(backend.transcribe_calls) == 1
    assert backend.transcribe_calls[0][0] == 2 * SAMPLE_RATE


def test_timestamp_fmt_mm_ss_below_one_hour(tmp_path: Path) -> None:
    """Pipeline picks ``fmt='MM:SS'`` for inputs shorter than 1 hour (AC-US-2.4)."""
    input_path = tmp_path / "short.mp3"
    input_path.write_bytes(b"")
    output_path = tmp_path / "short.md"

    captured: dict[str, TimestampFormat] = {}

    def capturing_render(
        segments: list[Segment],
        transcripts: list[TranscribedSegment],
        fmt: TimestampFormat,
    ) -> str:
        captured["fmt"] = fmt
        return "ok\n"

    backend = _FakeBackend()
    segmenter = _FakeSegmenter([Segment(0.0, 1.0, "speech")])
    pipeline = Pipeline(
        decode=lambda _p: _silence_pcm(59 * 60 + 59),  # 59:59
        segmenter=segmenter,
        backend=backend,
        render=capturing_render,
        model="tiny",
        device="cpu",
        lang="es",
        sample_rate=SAMPLE_RATE,
    )
    pipeline.run(input_path=input_path, output_path=output_path)

    assert captured["fmt"] == "MM:SS"


def test_timestamp_fmt_hh_mm_ss_at_or_above_one_hour(tmp_path: Path) -> None:
    """Pipeline picks ``fmt='HH:MM:SS'`` for inputs ≥ 1 hour (AC-US-2.4 / EC-4)."""
    input_path = tmp_path / "long.mp3"
    input_path.write_bytes(b"")
    output_path = tmp_path / "long.md"

    captured: dict[str, TimestampFormat] = {}

    def capturing_render(
        segments: list[Segment],
        transcripts: list[TranscribedSegment],
        fmt: TimestampFormat,
    ) -> str:
        captured["fmt"] = fmt
        return "ok\n"

    backend = _FakeBackend()
    segmenter = _FakeSegmenter([Segment(0.0, 1.0, "speech")])
    pipeline = Pipeline(
        decode=lambda _p: _silence_pcm(60 * 60),  # 1:00:00 exactly
        segmenter=segmenter,
        backend=backend,
        render=capturing_render,
        model="tiny",
        device="cpu",
        lang="es",
        sample_rate=SAMPLE_RATE,
    )
    pipeline.run(input_path=input_path, output_path=output_path)

    assert captured["fmt"] == "HH:MM:SS"


def test_transcribed_segments_re_anchored_to_episode_time(tmp_path: Path) -> None:
    """Backend yields offsets relative to the segment slice; pipeline rebases
    them to absolute episode time before handing to the renderer (per
    :class:`TranscribedSegment` docstring + ADR-0004 streaming contract).
    """
    input_path = tmp_path / "episode.mp3"
    input_path.write_bytes(b"")
    output_path = tmp_path / "episode.md"

    seen: list[TranscribedSegment] = []

    def capturing_render(
        segments: list[Segment],
        transcripts: list[TranscribedSegment],
        fmt: TimestampFormat,
    ) -> str:
        seen.extend(transcripts)
        return "ok\n"

    backend = _FakeBackend(
        transcripts_per_call=[TranscribedSegment(0.1, 0.9, "hola")],
    )
    # Speech segment from 4.0s -> 6.0s; backend yields 0.1-0.9 within the slice;
    # episode-absolute should be 4.1-4.9.
    segmenter = _FakeSegmenter(
        [
            Segment(0.0, 4.0, "music"),
            Segment(4.0, 6.0, "speech"),
        ]
    )
    pipeline = Pipeline(
        decode=lambda _p: _silence_pcm(6.0),
        segmenter=segmenter,
        backend=backend,
        render=capturing_render,
        model="tiny",
        device="cpu",
        lang="es",
        sample_rate=SAMPLE_RATE,
    )
    pipeline.run(input_path=input_path, output_path=output_path)

    assert len(seen) == 1
    assert seen[0].start == pytest.approx(4.1)
    assert seen[0].end == pytest.approx(4.9)
    assert seen[0].text == "hola"


# ---------------------------------------------------------------------------
# POD-013 — progress bar wiring (ADR-0010 — pipeline-level, per-segment ticks)
# ---------------------------------------------------------------------------


def test_pipeline_advances_each_phase_task_once_POD_013(tmp_path: Path) -> None:
    """ADR-0010 — decode + segment are atomic phases (one tick each);
    transcribe ticks once per speech segment regardless of backend
    yield cadence. We capture the advance() calls on a recording
    Progress so we can assert the order + counts without rendering.
    """
    from podcast_script.progress import (
        DECODE_TASK,
        SEGMENT_TASK,
        TRANSCRIBE_TASK,
        make_progress,
    )

    input_path = tmp_path / "episode.mp3"
    input_path.write_bytes(b"")
    output_path = tmp_path / "episode.md"

    # Three speech segments → transcribe should tick three times.
    segments = [
        Segment(0.0, 1.0, "speech"),
        Segment(1.0, 2.0, "music"),
        Segment(2.0, 3.0, "speech"),
        Segment(3.0, 4.0, "speech"),
    ]
    pipeline, _backend, _segmenter = _make_pipeline(
        pcm=_silence_pcm(4.0),
        segments=segments,
    )

    bar = make_progress()
    advances: list[tuple[int, float]] = []
    real_advance = bar.advance

    def recording_advance(task_id: object, advance: float = 1.0) -> None:
        advances.append((int(task_id), advance))  # type: ignore[arg-type]
        real_advance(task_id, advance)  # type: ignore[arg-type]

    bar.advance = recording_advance  # type: ignore[method-assign]
    pipeline.progress = bar

    pipeline.run(input_path=input_path, output_path=output_path)

    decode_ticks = [a for a in advances if a[0] == DECODE_TASK]
    segment_ticks = [a for a in advances if a[0] == SEGMENT_TASK]
    transcribe_ticks = [a for a in advances if a[0] == TRANSCRIBE_TASK]

    assert len(decode_ticks) == 1, advances
    assert len(segment_ticks) == 1, advances
    # Three speech segments out of four total — transcribe ticks 3 times.
    assert len(transcribe_ticks) == 3, advances


def test_pipeline_sets_transcribe_total_to_speech_segment_count_POD_013(
    tmp_path: Path,
) -> None:
    """ADR-0010 — transcribe task total is set after the segmenter pass
    so the bar's percentage is meaningful. Six segments, two of them
    speech → transcribe.total == 2.
    """
    from podcast_script.progress import TRANSCRIBE_TASK, make_progress

    input_path = tmp_path / "episode.mp3"
    input_path.write_bytes(b"")
    output_path = tmp_path / "episode.md"

    segments = [
        Segment(0.0, 1.0, "noise"),
        Segment(1.0, 2.0, "speech"),
        Segment(2.0, 3.0, "music"),
        Segment(3.0, 4.0, "silence"),
        Segment(4.0, 5.0, "speech"),
        Segment(5.0, 6.0, "music"),
    ]
    pipeline, _backend, _segmenter = _make_pipeline(
        pcm=_silence_pcm(6.0),
        segments=segments,
    )
    bar = make_progress()
    pipeline.progress = bar

    pipeline.run(input_path=input_path, output_path=output_path)

    assert bar.tasks[TRANSCRIBE_TASK].total == 2


def test_pipeline_works_without_progress_bar_POD_013(tmp_path: Path) -> None:
    """``Pipeline.progress = None`` is the default — Tier 1 unit tests
    that don't pass a Progress must keep working unchanged. This
    guards against a regression where the orchestrator unconditionally
    dereferences the field.
    """
    input_path = tmp_path / "episode.mp3"
    input_path.write_bytes(b"")
    output_path = tmp_path / "episode.md"

    pipeline, _backend, _segmenter = _make_pipeline(
        pcm=_silence_pcm(2.0),
        segments=[Segment(0.0, 2.0, "speech")],
    )
    # Default — no progress wired
    pipeline.run(input_path=input_path, output_path=output_path)

    assert output_path.is_file()

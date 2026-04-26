"""Tests for C-Decode (POD-007).

The decoder is the first ffmpeg-touching module. Its public surface
returns an ``NDArray[float32]`` and raises typed exceptions per ADR-0006.
These tests pin the validation gates (AC-US-1.4 missing input, UC-1 E4
missing ffmpeg, AC-US-1.3 / UC-1 E5 ffmpeg failure), the canonical argv
shape (ADR-0016), the ``commands.txt`` debug seam (POD-024 prep), and
the EC-3 spaces+non-ASCII path requirement.
"""

from __future__ import annotations

import os
import shutil
import wave
from pathlib import Path

import numpy as np
import pytest

from podcast_script.decode import decode
from podcast_script.errors import DecodeError, InputIOError, UsageError

_TARGET_SAMPLE_RATE = 16_000

_ffmpeg_required = pytest.mark.skipif(
    shutil.which("ffmpeg") is None,
    reason="ffmpeg not on PATH (Tier-3-style decoder tests need a real ffmpeg)",
)


def _write_silent_wav(
    path: Path,
    *,
    seconds: float = 0.25,
    sample_rate: int = _TARGET_SAMPLE_RATE,
) -> int:
    """Write a mono 16-bit PCM WAV of ``seconds`` of silence; return frame count."""
    frames = int(seconds * sample_rate)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(b"\x00\x00" * frames)
    return frames


def test_decode_raises_input_io_error_when_input_missing_AC_US_1_4(tmp_path: Path) -> None:
    """AC-US-1.4 — missing input file → :class:`InputIOError` (exit 3)."""
    missing = tmp_path / "does-not-exist.mp3"
    with pytest.raises(InputIOError) as exc_info:
        decode(missing)
    assert str(missing) in str(exc_info.value)


def test_decode_raises_input_io_error_when_input_unreadable_AC_US_1_4(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-US-1.4 — *unreadable* input file → :class:`InputIOError` (exit 3).

    SRS UC-1 E1 spells out two distinct messages: ``not found`` and
    ``not readable``. ``Path.is_file()`` returns ``True`` for a file the
    user has no read permission on, so without an explicit access check
    that branch falls through to ffmpeg and surfaces as DecodeError
    (exit 4) — wrong exit code for a permission problem.

    Monkeypatching both ``shutil.which`` and ``os.access`` keeps this a
    true Tier-1 unit test: no real chmod, no real ffmpeg installation
    needed. Without the ``shutil.which`` fake the decoder's ffmpeg-on-PATH
    guard would raise UsageError on any box lacking ffmpeg, masking the
    InputIOError this test is supposed to pin.
    """
    f = tmp_path / "ep.mp3"
    f.write_bytes(b"\x00")
    real_access = os.access

    def fake_access(path: str | os.PathLike[str], mode: int) -> bool:
        # Only flip R_OK on our target input file. Other os.access calls
        # (e.g. inside Path.is_file()) must continue to reflect reality.
        if mode == os.R_OK and os.fspath(path) == str(f):
            return False
        return real_access(path, mode)

    monkeypatch.setattr(shutil, "which", lambda _name: "/fake/ffmpeg")
    monkeypatch.setattr(os, "access", fake_access)

    with pytest.raises(InputIOError) as exc_info:
        decode(f)
    assert "not readable" in str(exc_info.value)
    assert str(f) in str(exc_info.value)


def test_decode_raises_usage_error_when_ffmpeg_not_on_path_UC_1_E4(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UC-1 E4 — ``ffmpeg`` missing from PATH → :class:`UsageError` (exit 2).

    Per NFR-9 / SRS UC-1 E4 the ``ffmpeg``-on-PATH check is a usage error
    (exit 2), not a model/decode error — the user is expected to install
    ffmpeg per the README. The error message must name ``ffmpeg`` so the
    user can grep for it.
    """
    fake_input = tmp_path / "ep.mp3"
    fake_input.write_bytes(b"")  # existence is enough; we never reach decode
    monkeypatch.setattr(shutil, "which", lambda _name: None)

    with pytest.raises(UsageError) as exc_info:
        decode(fake_input)
    assert "ffmpeg" in str(exc_info.value)


@_ffmpeg_required
def test_decode_returns_float32_mono_16khz_pcm_ADR_0016(tmp_path: Path) -> None:
    """ADR-0016 — successful decode returns ``NDArray[float32]`` whose length
    matches input duration * 16 kHz, mono. Silence in -> silence out (all zeros).
    """
    wav = tmp_path / "silence.wav"
    frames = _write_silent_wav(wav, seconds=0.25)

    pcm = decode(wav)

    assert pcm.dtype == np.float32
    assert pcm.ndim == 1
    # ffmpeg resampling has a small transient on the boundary; allow ±1 frame slack.
    assert abs(pcm.shape[0] - frames) <= 1
    assert np.all(pcm == 0.0)


@_ffmpeg_required
def test_decode_raises_decode_error_on_ffmpeg_failure_AC_US_1_3(tmp_path: Path) -> None:
    """AC-US-1.3 / UC-1 E5 / EC-10 — input ``ffmpeg`` cannot decode → :class:`DecodeError`.

    A ``.mp3``-named text file passes the input-existence guard but ffmpeg
    refuses to demux it, exiting non-zero. The error must surface as
    DecodeError (exit 4) and the message must name the input path so the
    operator can identify the offending file from the stderr line alone.
    """
    not_audio = tmp_path / "not-an-audio.mp3"
    not_audio.write_text("definitely not audio bytes\n", encoding="utf-8")

    with pytest.raises(DecodeError) as exc_info:
        decode(not_audio)
    assert str(not_audio) in str(exc_info.value)


@_ffmpeg_required
def test_decode_writes_commands_txt_when_debug_dir_given_AC_US_7_1(tmp_path: Path) -> None:
    """AC-US-7.1 — under ``--debug``, the executed ffmpeg argv is captured to
    ``commands.txt`` next to the decoded artifacts so the operator can replay
    the exact invocation. POD-024 (SP-6) wires the full ``--debug`` directory;
    POD-007 ships only the ``commands.txt`` seam.
    """
    wav = tmp_path / "silence.wav"
    _write_silent_wav(wav, seconds=0.1)
    debug_dir = tmp_path / "ep.debug"

    decode(wav, debug_dir=debug_dir)

    captured = (debug_dir / "commands.txt").read_text(encoding="utf-8")
    assert "ffmpeg" in captured
    assert str(wav) in captured
    # Canonical ADR-0016 markers must all appear in the captured argv:
    for token in ("-f f32le", f"-ar {_TARGET_SAMPLE_RATE}", "-ac 1", "-i"):
        assert token in captured, f"missing canonical token {token!r} in commands.txt"


@_ffmpeg_required
def test_decode_does_not_create_debug_dir_when_unset(tmp_path: Path) -> None:
    """When ``debug_dir`` is ``None`` (default), the decoder must not create
    sibling directories — POD-024 will own ``--debug`` lifecycle, and an
    eager mkdir here would surface as confusing leftovers from non-debug
    runs."""
    wav = tmp_path / "silence.wav"
    _write_silent_wav(wav, seconds=0.1)

    decode(wav)

    assert list(tmp_path.iterdir()) == [wav]


@_ffmpeg_required
def test_decode_handles_path_with_spaces_and_non_ascii_EC_3(tmp_path: Path) -> None:
    """EC-3 — input paths with spaces and non-ASCII characters MUST work
    end-to-end. The list-arg form of :func:`subprocess.run` already handles
    this on POSIX without additional quoting, but pinning it as a regression
    test guards future refactors that might reach for shell=True or string
    concatenation.
    """
    wav = tmp_path / "canción de prueba.wav"
    frames = _write_silent_wav(wav, seconds=0.1)

    pcm = decode(wav)

    assert pcm.dtype == np.float32
    assert abs(pcm.shape[0] - frames) <= 1

"""Tests for C-Decode (POD-007).

The decoder is the first ffmpeg-touching module. Its public surface
returns an ``NDArray[float32]`` and raises typed exceptions per ADR-0006.
These tests pin the validation gates (AC-US-1.4 missing input, UC-1 E4
missing ffmpeg, AC-US-1.3 / UC-1 E5 ffmpeg failure), the canonical argv
shape (ADR-0016), the ``commands.txt`` debug seam (POD-024 prep), and
the EC-3 spaces+non-ASCII path requirement.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from podcast_script.decode import decode
from podcast_script.errors import InputIOError, UsageError


def test_decode_raises_input_io_error_when_input_missing_AC_US_1_4(tmp_path: Path) -> None:
    """AC-US-1.4 — missing input file → :class:`InputIOError` (exit 3)."""
    missing = tmp_path / "does-not-exist.mp3"
    with pytest.raises(InputIOError) as exc_info:
        decode(missing)
    assert str(missing) in str(exc_info.value)


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

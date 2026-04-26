"""C-Decode (POD-007): ffmpeg → mono 16 kHz float32 PCM (ADR-0016).

Owns the single ffmpeg subprocess invocation used by the pipeline. The
canonical output format is locked by ADR-0016: raw little-endian float32
PCM at 16 kHz, mono, on stdout. ``decode()`` returns an ``NDArray`` view
over those bytes; downstream consumers (segmenter, Whisper backends)
read from the same buffer per ADR-0002 / ADR-0004.

Errors map to the typed-exception hierarchy in :mod:`.errors` (ADR-0006)
so the CLI alone is responsible for translating to ``typer.Exit(code)``:

- ``ffmpeg`` not on ``PATH`` → :class:`UsageError` (exit 2, UC-1 E4).
- Input path missing, not a file, or unreadable → :class:`InputIOError`
  (exit 3, AC-US-1.4 / UC-1 E1).
- ``ffmpeg`` exits non-zero → :class:`DecodeError` (exit 4, AC-US-1.3 /
  UC-1 E5 / EC-10).

The optional ``debug_dir`` is the seam POD-024 (SP-6) will use to wire
``--debug``; for POD-007 it only captures ``commands.txt`` per
AC-US-7.1.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path

import numpy as np
import numpy.typing as npt

from .errors import DecodeError, InputIOError, UsageError

# Canonical post-input ffmpeg argv (ADR-0016): raw little-endian float32 mono
# 16 kHz on stdout, banner suppressed, only true errors on stderr. The full
# argv prepends ``[ffmpeg_bin, "-i", str(input_path)]``; the leading binary
# path is resolved at call time via ``shutil.which`` so a missing ffmpeg
# fails as a UsageError rather than an internal FileNotFoundError.
_FFMPEG_ARGS_TAIL: tuple[str, ...] = (
    "-f",
    "f32le",
    "-ar",
    "16000",
    "-ac",
    "1",
    "-hide_banner",
    "-loglevel",
    "error",
    "-",
)


def decode(input_path: Path, *, debug_dir: Path | None = None) -> npt.NDArray[np.float32]:
    """Decode ``input_path`` to mono 16 kHz float32 PCM via ``ffmpeg``."""
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin is None:
        raise UsageError("ffmpeg not found on PATH; see README install steps")

    if not input_path.is_file():
        raise InputIOError(f"input file not found: {input_path}")
    if not os.access(input_path, os.R_OK):
        raise InputIOError(f"input file not readable: {input_path}")

    argv: list[str] = [ffmpeg_bin, "-i", str(input_path), *_FFMPEG_ARGS_TAIL]
    if debug_dir is not None:
        debug_dir.mkdir(parents=True, exist_ok=True)
        (debug_dir / "commands.txt").write_text(shlex.join(argv) + "\n", encoding="utf-8")

    completed = subprocess.run(argv, check=False, capture_output=True)
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace").strip()
        suffix = f": {stderr}" if stderr else ""
        raise DecodeError(
            f"ffmpeg failed (exit {completed.returncode}) decoding {input_path}{suffix}"
        )
    return np.frombuffer(completed.stdout, dtype=np.float32)

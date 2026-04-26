"""C-Decode (POD-007): ffmpeg → mono 16 kHz float32 PCM (ADR-0016).

Owns the single ffmpeg subprocess invocation used by the pipeline. The
canonical output format is locked by ADR-0016: raw little-endian float32
PCM at 16 kHz, mono, on stdout. ``decode()`` returns an ``NDArray`` view
over those bytes; downstream consumers (segmenter, Whisper backends)
read from the same buffer per ADR-0002 / ADR-0004.

Errors map to the typed-exception hierarchy in :mod:`.errors` (ADR-0006)
so the CLI alone is responsible for translating to ``typer.Exit(code)``:

- ``ffmpeg`` not on ``PATH`` → :class:`UsageError` (exit 2, UC-1 E4).
- Input path missing or not a file → :class:`InputIOError` (exit 3,
  AC-US-1.4 / UC-1 E1).
- ``ffmpeg`` exits non-zero → :class:`DecodeError` (exit 4, AC-US-1.3 /
  UC-1 E5 / EC-10).

The optional ``debug_dir`` is the seam POD-024 (SP-6) will use to wire
``--debug``; for POD-007 it only captures ``commands.txt`` per
AC-US-7.1.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import numpy.typing as npt

from .errors import InputIOError, UsageError


def decode(input_path: Path, *, debug_dir: Path | None = None) -> npt.NDArray[np.float32]:
    """Decode ``input_path`` to mono 16 kHz float32 PCM via ``ffmpeg``."""
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin is None:
        raise UsageError("ffmpeg not found on PATH; see README install steps")

    if not input_path.is_file():
        raise InputIOError(f"input file not found: {input_path}")

    raise NotImplementedError

"""Whisper backend Protocol surface (ADR-0003 / API-2).

The :class:`Pipeline` (POD-008) depends only on this Protocol; concrete
backends (``FasterWhisperBackend`` POD-019, ``MlxWhisperBackend`` POD-020)
implement it as siblings under :mod:`.`. Heavy library imports happen
inside each implementation's :meth:`WhisperBackend.load` per ADR-0011, so
nothing in this module triggers a TF / MLX import at CLI startup.

The Protocol is **internal**: SRS §9.3 explicitly does not commit it as a
stable public API for v1.0.0. ``select_backend`` (POD-018) lands later in
SP-3 and selects the concrete implementation by platform per ADR-0003.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import NamedTuple, Protocol

import numpy as np
import numpy.typing as npt


class TranscribedSegment(NamedTuple):
    """One contiguous transcribed slice of speech.

    ``start`` and ``end`` are seconds **relative to the start of the PCM
    array passed to** :meth:`WhisperBackend.transcribe`. The pipeline
    re-anchors them to absolute episode time (segment ``start`` + relative
    offset) before handing them to the renderer.
    """

    start: float
    end: float
    text: str


class WhisperBackend(Protocol):
    """Structural Protocol for Whisper inference backends (ADR-0003).

    Two concrete implementations land later in the plan:
    ``FasterWhisperBackend`` (POD-019) on Linux/CUDA/CPU, and
    ``MlxWhisperBackend`` (POD-020) on Apple Silicon. Tests substitute a
    fake backend that returns canned :class:`TranscribedSegment` lists.
    """

    name: str

    def load(self, model: str, device: str) -> None:
        """Eagerly resolve model weights (ADR-0009).

        On a cache miss this triggers the AC-US-5.1 first-run download
        notice within 1 s of pipeline start. On import / network / disk
        failure the implementation MUST raise
        :class:`~podcast_script.errors.ModelError` (exit 5).
        """
        ...

    def transcribe(
        self,
        pcm: npt.NDArray[np.float32],
        lang: str,
        sample_rate: int = 16000,
    ) -> Iterable[TranscribedSegment]:
        """Transcribe one speech-segment slice of mono float32 PCM.

        ``pcm`` is a contiguous slice (the pipeline carves it per speech
        segment for the streaming contract — ADR-0004). Implementations
        MAY yield iteratively or return a list; the pipeline only iterates
        the result.
        """
        ...

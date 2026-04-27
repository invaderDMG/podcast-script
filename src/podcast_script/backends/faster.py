"""C-FasterWhisper backend: ``WhisperBackend`` impl on Linux/CUDA/CPU (POD-019).

Implements :class:`~podcast_script.backends.base.WhisperBackend` (ADR-0003)
with a lazy ``faster_whisper`` import deferred to :meth:`FasterWhisperBackend.load`
per ADR-0011. The Pipeline (POD-008) calls ``load()`` immediately after
CLI validation per ADR-0009 so the AC-US-5.1 first-run notice fires
before decode (POD-021 ships the formal notice line).

``ImportError`` from the heavy chain (CTranslate2 / tokenizers / huggingface_hub)
and any cache / network / disk failure inside ``load()`` are wrapped in
:class:`~podcast_script.errors.ModelError` (exit 5) per ADR-0006 and
ADR-0011 Consequences — keeps the NFR-9 exit-code contract intact even
when the upstream library API drifts (R-17).
"""

from __future__ import annotations


class FasterWhisperBackend:
    """``faster-whisper``-backed implementation of :class:`WhisperBackend`.

    Construction is cheap — the heavy ``faster_whisper`` import does not
    happen until :meth:`load` is called (ADR-0011 first-use site). The
    ``transcribe`` method (POD-019 follow-up cycles) iterates the underlying
    ``WhisperModel.transcribe`` generator and re-shapes its output as
    :class:`TranscribedSegment` triples per ADR-0003.
    """

    name = "faster-whisper"

    def __init__(self) -> None:
        self._model: object | None = None
        self._model_name: str | None = None

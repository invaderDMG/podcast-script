"""Whisper backend Protocol surface + first-run notice helper (ADR-0003).

The :class:`Pipeline` (POD-008) depends only on this Protocol; concrete
backends (``FasterWhisperBackend`` POD-019, ``MlxWhisperBackend`` POD-020)
implement it as siblings under :mod:`.`. Heavy library imports happen
inside each implementation's :meth:`WhisperBackend.load` per ADR-0011, so
nothing in this module triggers a TF / MLX import at CLI startup.

The Protocol is **internal**: SRS §9.3 explicitly does not commit it as a
stable public API for v1.0.0. ``select_backend`` (POD-017) lands later in
SP-4 and selects the concrete implementation by platform per ADR-0003.

POD-021 adds the shared first-run download notice helper used by every
backend's ``load()``: :func:`emit_first_run_notice_if_missing` emits the
locked ``event=model_download`` line per ADR-0012 / AC-US-5.1 when the
caller's injected ``is_cached`` returns ``False``. Centralising the
emit-once logic here keeps faster + mlx mirrors free of duplication.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
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


# ---------------------------------------------------------------------------
# First-run download notice (POD-021 — AC-US-5.1 / AC-US-5.2 / ADR-0012)
# ---------------------------------------------------------------------------


MODEL_SIZES_GB: dict[str, float] = {
    "tiny": 0.075,
    "base": 0.14,
    "small": 0.46,
    "medium": 1.5,
    "large-v3": 3.0,
    "large-v3-turbo": 1.6,
}
"""Approximate on-disk sizes for the v1-supported Whisper models.

Used by :func:`emit_first_run_notice_if_missing` to populate the
``size_gb`` token of the locked ``event=model_download`` shape
(ADR-0012). Values are deliberately coarse — the precise indicator is
``huggingface_hub``'s download progress bar that follows the notice.
Adding a model post-v1 is a minor change; removing one is breaking.

Older Whisper variants (``large``, ``large-v1``, ``large-v2``) are
intentionally absent — passing one falls back to
:data:`_UNKNOWN_MODEL_SIZE_GB` so the user still sees a notice. Adding
them now would lock them into the v1.0.0 SemVer surface.
"""

_UNKNOWN_MODEL_SIZE_GB = 1.0
"""Fallback size used when the user passes a model name we don't track.

Conservative: the user gets warned a download may be coming, then sees
``huggingface_hub``'s real progress bar, rather than us silently letting
a multi-GB transfer surprise them.
"""


def emit_first_run_notice_if_missing(
    model: str,
    *,
    is_cached: Callable[[str], bool],
    logger: logging.Logger,
) -> None:
    """Emit the AC-US-5.1 first-run notice when ``model`` is not cached.

    Backends call this from their :meth:`WhisperBackend.load` BEFORE
    triggering the heavy library / network path so the NFR-6 1-s budget
    holds regardless of how slow ``huggingface_hub`` is. ``is_cached`` is
    injected as the cache-detection seam — Tier 2 contract tests
    (POD-030, SP-6) substitute a synthetic miss to verify the contract
    without touching the real HF cache.

    The emitted record carries the locked ADR-0012 shape: ``event``,
    ``model``, ``size_gb``. ``size_gb`` is rendered with ``{:g}`` so
    round numbers ship bare (``3``) and fractional sizes keep their
    decimals (``0.075``).
    """
    if is_cached(model):
        return
    size_gb = MODEL_SIZES_GB.get(model, _UNKNOWN_MODEL_SIZE_GB)
    logger.info(
        "",
        extra={
            "event": "model_download",
            "model": model,
            "size_gb": f"{size_gb:g}",
        },
    )

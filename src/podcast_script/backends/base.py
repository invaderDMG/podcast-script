"""Whisper backend Protocol surface + first-run notice helper + selector (ADR-0003).

The :class:`Pipeline` (POD-008) depends only on this Protocol; concrete
backends (``FasterWhisperBackend`` POD-019, ``MlxWhisperBackend`` POD-020)
implement it as siblings under :mod:`.`. Heavy library imports happen
inside each implementation's :meth:`WhisperBackend.load` per ADR-0011, so
nothing in this module triggers a TF / MLX import at CLI startup.

The Protocol is **internal**: SRS §9.3 explicitly does not commit it as a
stable public API for v1.0.0. :func:`select_backend` (POD-017) picks the
concrete implementation by platform per ADR-0003 and rejects the only
illegal pairing — ``--backend mlx-whisper`` off Apple Silicon (UC-1 E7).

POD-021 adds the shared first-run download notice helper used by every
backend's ``load()``: :func:`emit_first_run_notice_if_missing` emits the
locked ``event=model_download`` line per ADR-0012 / AC-US-5.1 when the
caller's injected ``is_cached`` returns ``False``. Centralising the
emit-once logic here keeps faster + mlx mirrors free of duplication.
"""

from __future__ import annotations

import logging
import platform
import sys
from collections.abc import Callable, Iterable
from typing import NamedTuple, Protocol

import numpy as np
import numpy.typing as npt

from ..errors import UsageError


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


# ---------------------------------------------------------------------------
# Backend selection (POD-017 — ADR-0003 / SRS §6 UC-1 E7)
# ---------------------------------------------------------------------------


def _machine() -> str:
    """Indirection over :func:`platform.machine` so tests can monkeypatch.

    ``select_backend`` consults :data:`sys.platform` and this function;
    monkeypatching the function is cheaper than mocking the whole
    :mod:`platform` module and keeps the test seam local to this file.
    """
    return platform.machine()


def select_backend(*, backend: str, device: str) -> WhisperBackend:
    """Pick the concrete :class:`WhisperBackend` implementation.

    Per ADR-0003 the rule is:

    * ``backend == "auto"``: ``arm64-darwin`` → mlx-whisper, else
      faster-whisper.
    * ``backend == "faster-whisper"``: always faster-whisper, on every
      platform (Apple Silicon users may opt into faster-whisper for
      portability over speed — Apple's MLX is faster on M-series chips
      but faster-whisper is a smaller dep stack).
    * ``backend == "mlx-whisper"`` off Apple Silicon: refused per
      SRS §6 UC-1 E7 (``UsageError``, exit 2). The constraint is a
      hard one — mlx-whisper depends on Apple's MLX framework which
      is darwin-arm64-only.

    ``device`` is accepted for API symmetry with the ``--device`` flag
    but isn't consulted here — the constraint UC-1 E7 covers is
    platform-only. The actual device handling happens inside each
    backend's :meth:`WhisperBackend.load` (``device="cuda"`` is
    rejected by faster-whisper at load time on a CPU-only host, etc.).

    The returned instance is *unloaded* — the caller (``Pipeline.run``)
    invokes :meth:`WhisperBackend.load` once during pipeline startup so
    the heavy library import happens at the right time per ADR-0011.
    The lazy-import pattern means importing :mod:`backends.base` itself
    does not pull in TF / MLX / faster-whisper.
    """
    del device  # see docstring — not part of the selection decision
    is_apple_silicon = sys.platform == "darwin" and _machine() == "arm64"

    if backend == "mlx-whisper" and not is_apple_silicon:
        raise UsageError(
            "--backend mlx-whisper requires Apple Silicon (arm64-darwin); "
            f"detected {sys.platform}/{_machine()}. "
            "Use --backend faster-whisper or --backend auto on this host."
        )

    if backend == "faster-whisper" or (backend == "auto" and not is_apple_silicon):
        from .faster import FasterWhisperBackend

        return FasterWhisperBackend()

    # Either backend == "mlx-whisper" on Apple Silicon, or
    # backend == "auto" on Apple Silicon — both pick mlx.
    from .mlx import MlxWhisperBackend

    return MlxWhisperBackend()

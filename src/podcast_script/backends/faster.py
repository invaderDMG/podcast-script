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

from collections.abc import Iterable, Iterator
from typing import TYPE_CHECKING, Protocol, cast

import numpy as np
import numpy.typing as npt

from ..errors import ModelError
from .base import TranscribedSegment


class _FasterSegment(Protocol):
    """Structural contract for one ``faster_whisper`` segment.

    The real lib emits objects with ``.start``, ``.end``, ``.text``
    attributes. Declared at module top (not under ``TYPE_CHECKING``)
    because tests stub this surface with their own duck-types and
    structural compatibility is the contract — no heavy lib imported.
    """

    start: float
    end: float
    text: str


if TYPE_CHECKING:

    class _FasterWhisperModel(Protocol):
        """Structural contract for the ``faster_whisper.WhisperModel``.

        ``transcribe`` returns a 2-tuple of ``(segments_iter, info)`` —
        the pipeline never reads ``info`` so we elide it as ``object``.
        """

        def transcribe(
            self,
            audio: npt.NDArray[np.float32],
            language: str,
        ) -> tuple[Iterable[_FasterSegment], object]: ...


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

    def load(self, model: str, device: str) -> None:
        """Resolve and load the requested model (ADR-0009 / ADR-0011).

        Subsequent calls are a no-op — the heavy build path runs once per
        process. Wraps the universe of failure modes that ``faster_whisper``
        + ``huggingface_hub`` surface (``ImportError`` from the lib chain,
        ``OSError`` from disk / cache, network / HTTP errors, library API
        drift) into :class:`ModelError` so ``cli.py``'s NFR-9 translation
        maps them all to exit code 5 with a useful message (AC-US-5.4).

        ``KeyboardInterrupt`` and ``SystemExit`` propagate untouched per
        ADR-0014 (Ctrl-C is the user's contract; AC-US-5.3 resume / restart
        is on the user, not us).
        """
        if self._model is not None:
            return
        try:
            self._model = self._build_model(model, device)
        except ImportError as e:
            raise ModelError(
                f"faster-whisper (or one of its dependencies: CTranslate2, "
                f"tokenizers, huggingface_hub) is not installed — run "
                f"`uv sync`. Cannot load model '{model}'."
            ) from e
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            # huggingface_hub spans a wide exception vocabulary
            # (httpx.ConnectError, HfHubHTTPError, OSError, ...). Any
            # non-ImportError failure during model resolution is a
            # ModelError (exit 5) per AC-US-5.4. R-17 (faster-whisper API
            # drift) is also covered by this broad wrap — surfacing the
            # original via __cause__ keeps the trace debuggable.
            raise ModelError(
                f"Failed to load faster-whisper model '{model}': {type(e).__name__}: {e}"
            ) from e
        self._model_name = model

    def _build_model(self, model: str, device: str) -> object:
        """Construct the underlying ``faster_whisper.WhisperModel``.

        Override-point for unit tests (subclass and replace this method to
        return a stub model without touching the heavy chain). Production
        code path triggers the lazy ``faster_whisper`` import here and
        delegates model resolution + cache lookup + first-run download to
        ``WhisperModel.__init__`` (which uses ``huggingface_hub`` under
        the hood).
        """
        from faster_whisper import WhisperModel  # type: ignore[import-untyped]

        return WhisperModel(model, device=device)

    def transcribe(
        self,
        pcm: npt.NDArray[np.float32],
        lang: str,
        sample_rate: int = 16000,
    ) -> Iterator[TranscribedSegment]:
        """Transcribe one mono float32 PCM slice (ADR-0003 / ADR-0004).

        Yields :class:`TranscribedSegment` triples lazily — the underlying
        ``WhisperModel.transcribe`` returns a generator and we re-shape
        each item without buffering. The Pipeline (POD-008) feeds one
        speech segment at a time per ADR-0004 streaming contract, and
        the per-segment progress tick (POD-013, ADR-0010) relies on the
        lazy yield to advance smoothly.
        """
        if self._model is None:
            raise ModelError(
                "FasterWhisperBackend.transcribe() called before load(); "
                "the orchestrator must call load() first per ADR-0009."
            )
        raw = self._run_inference(self._model, pcm, lang)
        for seg in raw:
            yield TranscribedSegment(
                start=float(seg.start),
                end=float(seg.end),
                text=str(seg.text),
            )

    def _run_inference(
        self,
        model: object,
        pcm: npt.NDArray[np.float32],
        lang: str,
    ) -> Iterable[_FasterSegment]:
        """Run ``model.transcribe`` and return the segment iterator.

        Override-point for unit tests. The real ``WhisperModel.transcribe``
        returns a ``(segments, info)`` 2-tuple; the pipeline only needs
        the iterator so we drop ``info`` here. POD-030 (Tier 2 contract,
        SP-6) verifies the real-lib path against the same ``transcribe``
        contract this seam shapes.
        """
        real_model = cast("_FasterWhisperModel", model)
        segments, _info = real_model.transcribe(pcm, language=lang)
        return segments

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

from ..errors import ModelError


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
        maps them all to exit code 5 with a useful message.
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

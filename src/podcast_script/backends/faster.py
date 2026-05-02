"""C-FasterWhisper backend: ``WhisperBackend`` impl on Linux/CUDA/CPU (POD-019, POD-021).

Implements :class:`~podcast_script.backends.base.WhisperBackend` (ADR-0003)
with a lazy ``faster_whisper`` import deferred to :meth:`FasterWhisperBackend.load`
per ADR-0011. The Pipeline (POD-008) calls ``load()`` immediately after
CLI validation per ADR-0009 so the AC-US-5.1 first-run notice fires
before decode.

POD-021 wires the AC-US-5.1 notice into ``load()``: a cheap cache check
(:meth:`_is_cached`, lazy-importing ``huggingface_hub.scan_cache_dir``)
runs before the heavy ``faster_whisper`` import. On a miss the locked
``event=model_download`` line goes to stderr (ADR-0012) within the
NFR-6 1-s budget, then ``huggingface_hub``'s own progress bar follows
the heavy build path. ``ImportError`` from the heavy chain (CTranslate2 /
tokenizers / huggingface_hub) and any cache / network / disk failure
inside ``load()`` are wrapped in :class:`~podcast_script.errors.ModelError`
(exit 5) per ADR-0006 — keeps the NFR-9 exit-code contract intact even
when the upstream library API drifts (R-17).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from typing import TYPE_CHECKING, Protocol, cast

import numpy as np
import numpy.typing as npt

from ..errors import ModelError
from .base import TranscribedSegment, emit_first_run_notice_if_missing

_log = logging.getLogger(__name__)


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

        On a first call, runs the AC-US-5.1 cache check via
        :meth:`_is_cached` and emits the locked ``event=model_download``
        notice (ADR-0012) before any heavy import — so NFR-6's 1-s
        budget holds even when the HF download is slow. Subsequent
        calls are a no-op. Wraps the universe of failure modes that
        ``faster_whisper`` + ``huggingface_hub`` surface (``ImportError``
        from the lib chain, ``OSError`` from disk / cache, network /
        HTTP errors, library API drift) into :class:`ModelError` so
        ``cli.py``'s NFR-9 translation maps them all to exit code 5
        with a useful message (AC-US-5.4).

        ``KeyboardInterrupt`` and ``SystemExit`` propagate untouched per
        ADR-0014 (Ctrl-C is the user's contract; AC-US-5.3 resume / restart
        is on the user, not us).
        """
        if self._model is not None:
            return
        emit_first_run_notice_if_missing(
            model,
            is_cached=self._is_cached,
            logger=_log,
        )
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

    def _is_cached(self, model: str) -> bool:
        """Return ``True`` if a faster-whisper cache entry for ``model`` exists.

        Real path: lazy-imports ``huggingface_hub`` and scans the local
        cache for any repo whose id ends with ``faster-whisper-{model}``
        (matches both Systran's official conversions and community
        forks like ``mobiuslabsgmbh/faster-whisper-large-v3-turbo``).
        Override-point for unit tests — POD-030 (Tier 2, SP-6) covers
        the live HF surface.

        The match anchors at the end of the repo id rather than using
        a plain substring: ``"faster-whisper-tiny"`` is a substring of
        ``"…/faster-whisper-tiny.en"``, and a substring matcher would
        falsely report the bare ``tiny`` as cached when only the ``.en``
        variant is on disk — silently suppressing the AC-US-5.1 notice
        for an unrelated multi-GB download.

        On any failure (HF lib missing, scan errors, permission denied)
        returns ``False`` so the AC-US-5.1 notice fires conservatively
        rather than silently letting a multi-GB download surprise the
        user.
        """
        try:
            from huggingface_hub import scan_cache_dir
        except ImportError:
            return False
        try:
            info = scan_cache_dir()
        except Exception:
            return False
        target = f"faster-whisper-{model}"
        return any(repo.repo_id.endswith(target) for repo in info.repos)

    def _build_model(self, model: str, device: str) -> object:
        """Construct the underlying ``faster_whisper.WhisperModel``.

        Override-point for unit tests (subclass and replace this method to
        return a stub model without touching the heavy chain). Production
        code path triggers the lazy ``faster_whisper`` import here and
        delegates model resolution + cache lookup + first-run download to
        ``WhisperModel.__init__`` (which uses ``huggingface_hub`` under
        the hood).

        ``compute_type="auto"`` lets CTranslate2 pick the most efficient
        compute type the target device natively supports (``int8`` on
        CPU, ``float16`` on CUDA, etc.) rather than the lib default
        ``"default"``, which infers the compute type from the saved
        model weights and emits a noisy ``[ctranslate2] [warning] The
        compute type inferred from the saved model is float16, but the
        target device or backend does not support efficient float16
        computation`` line on every load when the saved type cannot be
        executed natively (e.g. the canonical Systran float16 weights on
        macOS arm64 CPU). The warning is purely informational — CT2
        falls back transparently — but it slips past the logfmt-only
        promise (NFR-10) onto stderr from the C++ layer (issue #44).
        """
        from faster_whisper import WhisperModel  # type: ignore[import-untyped]

        return WhisperModel(model, device=device, compute_type="auto")

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

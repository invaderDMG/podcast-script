"""Tests for the C-FasterWhisper backend (POD-019).

Tier 1 unit tests per ADR-0017: the lazy-import boundary (ADR-0011),
the ``ImportError`` → :class:`ModelError` wrap (ADR-0006), and the
``transcribe()`` shape (ADR-0003 / ADR-0004) exercised against a
mocked engine seam. The real ``faster_whisper`` is never imported in
this suite — POD-030 (SP-6) lands the Tier 2 contract test that
runs against the actual library.
"""

from __future__ import annotations

import importlib
import sys

import numpy as np
import numpy.typing as npt
import pytest

from podcast_script.backends.base import TranscribedSegment
from podcast_script.errors import ModelError

SAMPLE_RATE = 16_000


def _silence_pcm(duration_s: float) -> npt.NDArray[np.float32]:
    return np.zeros(int(duration_s * SAMPLE_RATE), dtype=np.float32)

# ---------------------------------------------------------------------------
# ADR-0011 — module-level lazy-import boundary
# ---------------------------------------------------------------------------


def test_module_does_not_eagerly_import_faster_whisper() -> None:
    """ADR-0011: ``backends/faster.py`` MUST NOT import ``faster_whisper``
    at module top — the heavy CTranslate2 / tokenizers chain is deferred
    to first-use inside :meth:`FasterWhisperBackend.load`. Importing the
    module (e.g. for ``select_backend`` resolution at CLI startup) must
    not trigger the cold-import cost.
    """
    sys.modules.pop("podcast_script.backends.faster", None)
    sys.modules.pop("faster_whisper", None)

    importlib.import_module("podcast_script.backends.faster")

    assert "faster_whisper" not in sys.modules


def test_constructor_does_not_import_faster_whisper() -> None:
    """ADR-0011: instantiating the backend MUST be cheap — the heavy
    library is loaded only when :meth:`load` is called. Companion to the
    module-level test: this guards the *class-construction* boundary.
    """
    sys.modules.pop("faster_whisper", None)

    from podcast_script.backends.faster import FasterWhisperBackend

    backend = FasterWhisperBackend()

    assert backend.name == "faster-whisper"
    assert "faster_whisper" not in sys.modules


# ---------------------------------------------------------------------------
# ADR-0006 / ADR-0011 Consequences — ImportError wrap inside load()
# ---------------------------------------------------------------------------


class _StubFasterBackend:
    """Test seam over ``FasterWhisperBackend`` that overrides the loader.

    Subclasses the real backend so we can stub :meth:`_build_model` without
    touching the heavy ``faster_whisper`` import. Mirrors the
    ``_StubInaSegmenter`` pattern in ``tests/test_segment.py``.
    """


def _make_backend_with_build_error(error: Exception) -> object:
    """Build a backend whose ``_build_model`` raises ``error`` on load.

    Helper kept here (rather than in conftest) because no other test file
    needs it; POD-030 (Tier 2 contract) tests will run against the real
    backend, not via this seam.
    """
    from podcast_script.backends.faster import FasterWhisperBackend

    class _ErrorBackend(FasterWhisperBackend):
        def _build_model(self, model: str, device: str) -> object:
            raise error

    return _ErrorBackend()


def test_load_wraps_import_error_in_model_error() -> None:
    """ADR-0011 Consequences: an ``ImportError`` from the heavy chain
    (CTranslate2 / tokenizers / faster_whisper itself) MUST surface as
    :class:`ModelError` (exit 5) so ``cli.py``'s NFR-9 mapping translates
    it to the published exit-code contract instead of the unexpected
    fallback (exit 1).
    """
    backend = _make_backend_with_build_error(
        ImportError("No module named 'faster_whisper'"),
    )

    with pytest.raises(ModelError) as exc_info:
        backend.load(model="tiny", device="cpu")  # type: ignore[attr-defined]

    assert isinstance(exc_info.value.__cause__, ImportError)
    assert "faster-whisper" in str(exc_info.value)


def test_load_caches_model_across_calls() -> None:
    """ADR-0011 first-use site: a second :meth:`load` call MUST NOT
    re-invoke the heavy build path. The Pipeline calls ``load()`` once
    per run today (ADR-0009), but in-process re-use (e.g. a future batch
    mode) must not pay the cost twice.
    """
    from podcast_script.backends.faster import FasterWhisperBackend

    build_calls = 0

    class _CountingBackend(FasterWhisperBackend):
        def _build_model(self, model: str, device: str) -> object:
            nonlocal build_calls
            build_calls += 1
            return object()

    backend = _CountingBackend()
    backend.load(model="tiny", device="cpu")
    backend.load(model="tiny", device="cpu")

    assert build_calls == 1


# ---------------------------------------------------------------------------
# ADR-0003 / ADR-0004 — transcribe() shape (Iterable[TranscribedSegment])
# ---------------------------------------------------------------------------


class _FakeFasterSegment:
    """Stand-in for a ``faster_whisper`` segment object.

    The real lib emits objects with ``.start``, ``.end``, ``.text``
    attributes; this minimal duck-type captures that surface so the unit
    test can drive ``transcribe()`` without importing CTranslate2.
    """

    def __init__(self, start: float, end: float, text: str) -> None:
        self.start = start
        self.end = end
        self.text = text


def _make_backend_with_canned_segments(
    segments: list[_FakeFasterSegment],
) -> object:
    """Build a backend whose loaded ``_model`` returns ``segments``.

    Mirrors how ``faster_whisper.WhisperModel.transcribe`` returns
    ``(segments_iter, info)`` — the seam is the ``_run_inference`` hook
    so unit tests don't depend on the lib's API shape.
    """
    from podcast_script.backends.faster import FasterWhisperBackend

    class _CannedBackend(FasterWhisperBackend):
        def _build_model(self, model: str, device: str) -> object:
            return object()  # opaque sentinel — _run_inference ignores it

        def _run_inference(
            self,
            model: object,
            pcm: npt.NDArray[np.float32],
            lang: str,
        ) -> object:
            return iter(segments)

    backend = _CannedBackend()
    backend.load(model="tiny", device="cpu")  # type: ignore[attr-defined]
    return backend


def test_transcribe_yields_typed_segments() -> None:
    """ADR-0003: ``transcribe`` MUST yield :class:`TranscribedSegment`
    triples (``start``, ``end``, ``text``) — not the raw library type.
    The Pipeline (POD-008) consumes the abstraction, never the lib.
    """
    canned = [
        _FakeFasterSegment(start=0.0, end=2.5, text="hola"),
        _FakeFasterSegment(start=2.5, end=4.0, text="qué tal"),
    ]
    backend = _make_backend_with_canned_segments(canned)

    out = list(backend.transcribe(_silence_pcm(4.0), lang="es"))  # type: ignore[attr-defined]

    assert out == [
        TranscribedSegment(start=0.0, end=2.5, text="hola"),
        TranscribedSegment(start=2.5, end=4.0, text="qué tal"),
    ]


def test_transcribe_streams_lazily_per_ADR_0004() -> None:
    """ADR-0004: ``transcribe`` is a streaming contract — segments are
    yielded one-by-one, not buffered. The Pipeline relies on this for
    per-segment progress ticks (POD-013, ADR-0010). Stub the underlying
    iterator so we can assert items arrive incrementally.
    """
    yielded_count = 0

    def _generator() -> object:
        nonlocal yielded_count
        for seg in [
            _FakeFasterSegment(0.0, 1.0, "uno"),
            _FakeFasterSegment(1.0, 2.0, "dos"),
        ]:
            yielded_count += 1
            yield seg

    from podcast_script.backends.faster import FasterWhisperBackend

    class _StreamingBackend(FasterWhisperBackend):
        def _build_model(self, model: str, device: str) -> object:
            return object()

        def _run_inference(
            self,
            model: object,
            pcm: npt.NDArray[np.float32],
            lang: str,
        ) -> object:
            return _generator()

    backend = _StreamingBackend()
    backend.load(model="tiny", device="cpu")
    stream = backend.transcribe(_silence_pcm(2.0), lang="es")

    # Pull the first item — only one upstream segment should have been
    # consumed at this point (lazy streaming, not eager buffering).
    first = next(iter(stream))
    assert first.text == "uno"
    assert yielded_count == 1


def test_transcribe_before_load_raises_model_error() -> None:
    """Calling :meth:`transcribe` before :meth:`load` is a programming
    error in the orchestrator (the Pipeline always calls ``load()``
    first per ADR-0009). Surface as :class:`ModelError` rather than a
    ``None``-attribute traceback so the cli's NFR-9 mapping holds.
    """
    from podcast_script.backends.faster import FasterWhisperBackend

    backend = FasterWhisperBackend()

    with pytest.raises(ModelError, match="load"):
        list(backend.transcribe(_silence_pcm(1.0), lang="es"))

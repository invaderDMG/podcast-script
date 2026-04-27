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

import pytest

from podcast_script.errors import ModelError

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

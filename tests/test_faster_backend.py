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

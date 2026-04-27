"""Tests for the C-MlxWhisper backend (POD-020).

Tier 1 unit tests per ADR-0017: the lazy-import boundary (ADR-0011),
the ``ImportError`` → :class:`ModelError` wrap (ADR-0006), the
``transcribe()`` shape (ADR-0003 / ADR-0004), and the AC-US-5.1 /
AC-US-5.2 first-run model-download notice exercised against a mocked
cache-detection seam. Mirrors :mod:`tests.test_faster_backend` for the
sibling ``MlxWhisperBackend`` — the real ``mlx_whisper`` is never
imported in this suite (POD-030 lands the Tier 2 contract test against
the actual library on the macOS CI lane).
"""

from __future__ import annotations

import importlib
import sys

# ---------------------------------------------------------------------------
# ADR-0011 — module-level lazy-import boundary
# ---------------------------------------------------------------------------


def test_module_does_not_eagerly_import_mlx_whisper() -> None:
    """ADR-0011: ``backends/mlx.py`` MUST NOT import ``mlx_whisper`` at
    module top — the heavy MLX / torch / numba chain is deferred to
    first-use inside :meth:`MlxWhisperBackend.load`. Importing the module
    (e.g. for ``select_backend`` resolution at CLI startup) must not
    trigger the cold-import cost on Apple Silicon.
    """
    sys.modules.pop("podcast_script.backends.mlx", None)
    sys.modules.pop("mlx_whisper", None)

    importlib.import_module("podcast_script.backends.mlx")

    assert "mlx_whisper" not in sys.modules


def test_constructor_does_not_import_mlx_whisper() -> None:
    """ADR-0011: instantiating the backend MUST be cheap — the heavy
    library is loaded only when :meth:`load` is called. Companion to the
    module-level test: this guards the *class-construction* boundary.
    """
    sys.modules.pop("mlx_whisper", None)

    from podcast_script.backends.mlx import MlxWhisperBackend

    backend = MlxWhisperBackend()

    assert backend.name == "mlx-whisper"
    assert "mlx_whisper" not in sys.modules

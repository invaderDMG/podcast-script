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

import pytest

from podcast_script.backends.mlx import MlxWhisperBackend
from podcast_script.errors import ModelError

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


# ---------------------------------------------------------------------------
# ADR-0006 / ADR-0011 Consequences — ImportError wrap inside load()
# ---------------------------------------------------------------------------


def _make_backend_with_build_error(error: Exception) -> MlxWhisperBackend:
    """Build a backend whose ``_build_model`` raises ``error`` on load.

    Helper kept here (rather than in conftest) because no other test file
    needs it; POD-030 (Tier 2 contract) tests will run against the real
    backend, not via this seam.
    """

    class _ErrorBackend(MlxWhisperBackend):
        def _build_model(self, model: str, device: str) -> object:
            raise error

    return _ErrorBackend()


def test_load_wraps_import_error_in_model_error() -> None:
    """ADR-0011 Consequences: an ``ImportError`` from the heavy chain
    (``mlx``, ``mlx_whisper``, ``huggingface_hub``) MUST surface as
    :class:`ModelError` (exit 5) so ``cli.py``'s NFR-9 mapping translates
    it to the published exit-code contract instead of the unexpected
    fallback (exit 1).
    """
    backend = _make_backend_with_build_error(
        ImportError("No module named 'mlx_whisper'"),
    )

    with pytest.raises(ModelError) as exc_info:
        backend.load(model="tiny", device="cpu")

    assert isinstance(exc_info.value.__cause__, ImportError)
    assert "mlx-whisper" in str(exc_info.value)


def test_load_caches_model_across_calls() -> None:
    """ADR-0011 first-use site: a second :meth:`load` call MUST NOT
    re-invoke the heavy build path. The Pipeline calls ``load()`` once
    per run today (ADR-0009), but in-process re-use (e.g. a future batch
    mode) must not pay the cost twice.
    """
    build_calls = 0

    class _CountingBackend(MlxWhisperBackend):
        def _build_model(self, model: str, device: str) -> object:
            nonlocal build_calls
            build_calls += 1
            return object()

    backend = _CountingBackend()
    backend.load(model="tiny", device="cpu")
    backend.load(model="tiny", device="cpu")

    assert build_calls == 1

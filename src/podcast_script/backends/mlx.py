"""C-MlxWhisper backend: ``WhisperBackend`` impl on Apple Silicon (POD-020).

Mirror of :mod:`podcast_script.backends.faster` for the macOS arm64
platform. Implements :class:`~podcast_script.backends.base.WhisperBackend`
(ADR-0003) with a lazy ``mlx_whisper`` import deferred to
:meth:`MlxWhisperBackend.load` per ADR-0011 — the heavy
``mlx_whisper`` / ``mlx`` / ``numba`` chain stays out of CLI startup so
``select_backend`` (POD-017, SP-4) can probe both backends without
paying either one's cold-import cost.

The Pipeline (POD-008) calls ``load()`` immediately after CLI validation
per ADR-0009, which is also where the AC-US-5.1 first-run notice fires
through the shared :func:`~.base.emit_first_run_notice_if_missing`
helper. ``ImportError`` from the heavy chain (``mlx``, ``mlx_whisper``,
``huggingface_hub``) and any cache / network / disk failure inside
``load()`` are wrapped in :class:`~podcast_script.errors.ModelError`
(exit 5) per ADR-0006, keeping the NFR-9 exit-code contract intact even
when the upstream library API drifts (R-17).
"""

from __future__ import annotations

import logging

from ..errors import ModelError
from .base import emit_first_run_notice_if_missing

_log = logging.getLogger(__name__)


class MlxWhisperBackend:
    """``mlx-whisper``-backed implementation of
    :class:`~podcast_script.backends.base.WhisperBackend` for Apple Silicon.

    Construction is cheap — the heavy ``mlx_whisper`` import does not
    happen until :meth:`load` is called (ADR-0011 first-use site). The
    ``transcribe`` method (POD-020 follow-up cycle) iterates the
    underlying ``mlx_whisper.transcribe`` segments and re-shapes them as
    :class:`~podcast_script.backends.base.TranscribedSegment` triples
    per ADR-0003.
    """

    name = "mlx-whisper"

    def __init__(self) -> None:
        self._model: object | None = None
        self._model_name: str | None = None

    def load(self, model: str, device: str) -> None:
        """Resolve and load the requested model (ADR-0009 / ADR-0011).

        Subsequent calls are a no-op (cached model). Wraps
        ``ImportError`` from the heavy ``mlx_whisper`` / ``mlx`` /
        ``huggingface_hub`` chain into :class:`ModelError` so
        ``cli.py``'s NFR-9 translation maps it to exit code 5 with a
        useful message instead of the unexpected-internal fallback.

        ``device`` is accepted for Protocol symmetry with
        :class:`~podcast_script.backends.faster.FasterWhisperBackend`
        but unused: ``mlx_whisper`` always runs on the unified-memory
        Apple Silicon GPU.
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
                f"mlx-whisper (or one of its dependencies: mlx, "
                f"huggingface_hub) is not installed — run `uv sync` on "
                f"an Apple Silicon machine. Cannot load model '{model}'."
            ) from e
        self._model_name = model

    def _is_cached(self, model: str) -> bool:
        """Return ``True`` if an mlx-whisper cache entry for ``model`` exists.

        Real path: lazy-imports ``huggingface_hub`` and scans the local
        cache for any repo whose id ends with ``/whisper-{model}``. The
        leading slash is load-bearing — it disambiguates ``mlx-community``
        repos (``mlx-community/whisper-tiny``) from the faster-whisper
        siblings (``Systran/faster-whisper-tiny``) that share the same
        ``~/.cache/huggingface`` directory. Without the slash anchor,
        a faster cache entry would falsely report the mlx model as
        cached and silently suppress the AC-US-5.1 notice.

        Override-point for unit tests — POD-030 (Tier 2, SP-6) covers
        the live HF surface on macOS CI.

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
        target = f"/whisper-{model}"
        return any(repo.repo_id.endswith(target) for repo in info.repos)

    def _build_model(self, model: str, device: str) -> object:
        """Construct (download + load) the underlying ``mlx_whisper`` model.

        Override-point for unit tests (subclass and replace this method
        to return a stub model without touching the heavy chain).
        Production code path triggers the lazy ``mlx_whisper`` import
        here and delegates HF cache lookup + first-run download to
        ``mlx_whisper.load_models.load_model``.
        """
        # ``mlx_whisper`` is darwin-arm64-only via the PEP 508 marker
        # in ``pyproject.toml``; ``[[tool.mypy.overrides]]`` waives
        # missing-imports and missing-stubs uniformly across CI
        # platforms (Ubuntu: not installed; macOS: installed, untyped).
        from mlx_whisper.load_models import load_model

        return load_model(model)

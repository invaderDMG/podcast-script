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


class MlxWhisperBackend:
    """``mlx-whisper``-backed implementation of
    :class:`~podcast_script.backends.base.WhisperBackend` for Apple Silicon.

    Construction is cheap — the heavy ``mlx_whisper`` import does not
    happen until :meth:`load` is called (ADR-0011 first-use site). The
    later TDD cycles in POD-020 add :meth:`load` and :meth:`transcribe`
    on top of this skeleton.
    """

    name = "mlx-whisper"

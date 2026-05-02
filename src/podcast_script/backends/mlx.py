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
from collections.abc import Iterable, Iterator, Mapping
from typing import Any, Protocol

import numpy as np
import numpy.typing as npt

from ..errors import ModelError
from .base import TranscribedSegment, emit_first_run_notice_if_missing

_log = logging.getLogger(__name__)

_CANONICAL_MLX_REPOS: dict[str, str] = {
    # Verified against `https://huggingface.co/api/models/<repo>` on
    # 2026-05-02. The mlx-community org applies the ``-mlx`` suffix
    # asymmetrically — ``tiny`` ships under both `whisper-tiny` and
    # `whisper-tiny-mlx`, ``large-v3-turbo`` ships only without the
    # suffix, and the rest are ``-mlx``-only. The v0.1.2 prefix-rule
    # fix (`mlx-community/whisper-{model}` for every shortname) 404'd
    # on `base`, `small`, `medium`, `large-v3` because those repos
    # only exist with the suffix; the inverse rule (always append
    # `-mlx`) would 404 on `large-v3-turbo`. Explicit table is the
    # only way the matrix closes (issue #45 v2).
    #
    # ``tiny`` deliberately maps to the unsuffixed repo to match the
    # cache convention seeded by every prior release — flipping it to
    # ``-mlx`` would re-trigger a download notice for users who
    # already have ``mlx-community/whisper-tiny`` on disk.
    "tiny": "mlx-community/whisper-tiny",
    "base": "mlx-community/whisper-base-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "large-v3": "mlx-community/whisper-large-v3-mlx",
    "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
}
"""Shortname → canonical ``mlx-community`` HF repo id mapping.

Mirrors :data:`podcast_script.config.SUPPORTED_MODELS`. When a future
Whisper variant lands and is added to ``SUPPORTED_MODELS``, the
maintainer probes the HF API and adds a row here in the same commit
— see the runbook entry in ``CHANGELOG.md`` ``### Maintainer runbook``.
"""

_MLX_COMMUNITY_PREFIX = "mlx-community/whisper-"
"""Best-effort prefix for shortnames not in :data:`_CANONICAL_MLX_REPOS`.

Forward-compat fallback only — keeps the door open for a
``--model <new-shortname>`` that landed in upstream Whisper but has not
yet been added to the canonical table. Users hitting this branch get
the same 404 they would have on v0.1.2 if mlx-community has not
converted the model; intentional, since the alternative is hard-coding
"likely" naming and silently misdirecting the download.
"""


def _resolve_repo_id(model: str) -> str:
    """Map a Whisper shortname (``large-v3``) to its mlx-community repo id.

    Three branches:

    1. **Pass-through** for anything containing ``"/"`` — already a
       fully-qualified HF repo id (``mlx-community/whisper-large-v3-q4``)
       or a local filesystem path. The power-user override surface.
    2. **Canonical table lookup** for the v1-supported shortnames in
       :data:`_CANONICAL_MLX_REPOS`. The naming asymmetry across the
       mlx-community org (some models ``-mlx``-suffixed, some not) is
       too irregular for a prefix rule.
    3. **Best-effort prefix** for unknown shortnames — same shape as
       the v0.1.2 fallback. Forward-compat for shortnames added to
       upstream Whisper after this release.
    """
    if "/" in model:
        return model
    if model in _CANONICAL_MLX_REPOS:
        return _CANONICAL_MLX_REPOS[model]
    return f"{_MLX_COMMUNITY_PREFIX}{model}"


class _MlxSegment(Protocol):
    """Structural contract for one mlx-whisper segment.

    ``mlx_whisper.transcribe`` returns dicts in its ``"segments"`` list;
    ``_run_inference`` adapts them into objects matching this Protocol
    so :meth:`MlxWhisperBackend.transcribe` is symmetric with the
    faster-whisper sibling. Declared at module top (not under
    ``TYPE_CHECKING``) so unit tests can stub the surface with their
    own duck-types — structural compatibility is the contract.
    """

    start: float
    end: float
    text: str


class _MlxSegmentTriple:
    """Concrete :class:`_MlxSegment` used by the production path.

    The real-library branch of :meth:`MlxWhisperBackend._run_inference`
    wraps each ``mlx_whisper`` segment dict in one of these — turning
    ``seg["start"]`` into ``triple.start`` so :meth:`.transcribe` can
    consume any :class:`_MlxSegment` (real triples or test fakes) by
    attribute access. A plain class (not :class:`NamedTuple` /
    ``frozen=True`` dataclass) is used so the read-only-vs-settable
    variance check in :class:`_MlxSegment` stays satisfied without
    declaring every attribute as a ``@property``.
    """

    __slots__ = ("end", "start", "text")

    def __init__(self, start: float, end: float, text: str) -> None:
        self.start = start
        self.end = end
        self.text = text


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

        On a first call, runs the AC-US-5.1 cache check via
        :meth:`_is_cached` and emits the locked ``event=model_download``
        notice (ADR-0012) before any heavy import — so NFR-6's 1-s
        budget holds even when the HF download is slow. Subsequent
        calls are a no-op. Wraps the universe of failure modes that
        ``mlx_whisper`` + ``huggingface_hub`` surface (``ImportError``
        from the lib chain, ``OSError`` from disk / cache, network /
        HTTP errors, library API drift) into :class:`ModelError` so
        ``cli.py``'s NFR-9 translation maps them all to exit code 5
        with a useful message (AC-US-5.4).

        ``KeyboardInterrupt`` and ``SystemExit`` propagate untouched per
        ADR-0014 (Ctrl-C is the user's contract; AC-US-5.3 resume /
        restart is on the user, not us).

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
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            # huggingface_hub spans a wide exception vocabulary
            # (httpx.ConnectError, HfHubHTTPError, OSError, ...). Any
            # non-ImportError failure during model resolution is a
            # ModelError (exit 5) per AC-US-5.4. R-17 (mlx-whisper API
            # drift) is also covered by this broad wrap — surfacing the
            # original via __cause__ keeps the trace debuggable.
            raise ModelError(
                f"Failed to load mlx-whisper model '{model}': {type(e).__name__}: {e}"
            ) from e
        # Store the resolved repo id (not the bare shortname) so
        # ``_run_inference``'s ``path_or_hf_repo`` lookup hits the same
        # HF repo ``_build_model`` just resolved — issue #45.
        self._model_name = _resolve_repo_id(model)

    def _is_cached(self, model: str) -> bool:
        """Return ``True`` if an mlx-whisper cache entry for ``model`` exists.

        Real path: lazy-imports ``huggingface_hub`` and scans the local
        cache for any repo whose id ends with ``/<leaf>`` where
        ``<leaf>`` is the basename of the resolved repo id from
        :func:`_resolve_repo_id` (e.g. ``whisper-large-v3-mlx`` for
        shortname ``large-v3``, ``whisper-large-v3-turbo`` for
        ``large-v3-turbo``). The leading slash is load-bearing — it
        disambiguates ``mlx-community`` repos from the faster-whisper
        siblings (``Systran/faster-whisper-tiny``) that share the same
        ``~/.cache/huggingface`` directory. Without the slash anchor,
        a faster cache entry would falsely report the mlx model as
        cached and silently suppress the AC-US-5.1 notice.

        The previous v0.1.2 implementation hard-coded the anchor as
        ``f"/whisper-{model}"`` — which silently broke for the
        ``-mlx``-suffixed repos (``base``, ``small``, ``medium``,
        ``large-v3``): a cache populated with
        ``mlx-community/whisper-large-v3-mlx`` does not end with
        ``/whisper-large-v3``, so AC-US-5.2's silence path was bypassed
        on every warm run for those four shortnames (issue #45 v2).

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
        leaf = _resolve_repo_id(model).rsplit("/", 1)[-1]
        target = f"/{leaf}"
        return any(repo.repo_id.endswith(target) for repo in info.repos)

    def _build_model(self, model: str, device: str) -> object:
        """Construct (download + load) the underlying ``mlx_whisper`` model.

        Override-point for unit tests (subclass and replace this method
        to return a stub model without touching the heavy chain).
        Production code path triggers the lazy ``mlx_whisper`` import
        here and delegates HF cache lookup + first-run download to
        ``mlx_whisper.load_models.load_model``.

        The bare shortname is resolved to the canonical
        ``mlx-community/whisper-<shortname>`` HF repo id via
        :func:`_resolve_repo_id` before the lookup — ``load_model``
        accepts either a local path or a fully-qualified repo id, and a
        bare shortname like ``"large-v3"`` 404s on the HF API (issue #45).
        """
        # ``mlx_whisper`` is darwin-arm64-only via the PEP 508 marker
        # in ``pyproject.toml``; ``[[tool.mypy.overrides]]`` waives
        # missing-imports and missing-stubs uniformly across CI
        # platforms (Ubuntu: not installed; macOS: installed, untyped).
        from mlx_whisper.load_models import load_model

        return load_model(_resolve_repo_id(model))

    def transcribe(
        self,
        pcm: npt.NDArray[np.float32],
        lang: str,
        sample_rate: int = 16000,
    ) -> Iterator[TranscribedSegment]:
        """Transcribe one mono float32 PCM slice (ADR-0003 / ADR-0004).

        Yields :class:`TranscribedSegment` triples lazily — the
        underlying ``_run_inference`` is iterable, and we re-shape each
        item without buffering. The Pipeline (POD-008) feeds one speech
        segment at a time per ADR-0004 streaming contract, and the
        per-segment progress tick (POD-013, ADR-0010) relies on the lazy
        yield to advance smoothly.
        """
        if self._model is None:
            raise ModelError(
                "MlxWhisperBackend.transcribe() called before load(); "
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
    ) -> Iterable[_MlxSegment]:
        """Run ``mlx_whisper.transcribe`` and yield duck-typed segments.

        Override-point for unit tests. ``mlx_whisper.transcribe`` is a
        function (not a method on the loaded model); it returns a dict
        with a ``"segments"`` list of dicts. We adapt those dicts into
        :class:`_MlxSegmentTriple` instances so :meth:`transcribe` can
        consume the same attribute interface as the faster-whisper
        sibling.

        ``model`` is unused here — ``mlx_whisper.transcribe`` re-loads
        from ``path_or_hf_repo`` each call (it has its own module-level
        cache); we pass ``self._model_name`` for that purpose. The
        argument is kept for seam symmetry with the faster sibling.
        """
        import mlx_whisper

        if self._model_name is None:
            raise ModelError(
                "MlxWhisperBackend internal state is invalid: _model_name unset after load()."
            )
        result: Mapping[str, Any] = mlx_whisper.transcribe(
            pcm,
            path_or_hf_repo=self._model_name,
            language=lang,
        )
        for seg in result.get("segments", []):
            yield _MlxSegmentTriple(
                start=float(seg["start"]),
                end=float(seg["end"]),
                text=str(seg["text"]),
            )

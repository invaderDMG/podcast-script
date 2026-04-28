"""C-Segment stage: ``Segmenter`` Protocol + ``inaSpeechSegmenter`` impl.

The :class:`Pipeline` (POD-008) depends on the :class:`Segmenter` Protocol
and the :class:`Segment` dataclass declared here.  POD-010 adds the
concrete :class:`InaSpeechSegmenter` implementation, with the heavy
TensorFlow / ``inaSpeechSegmenter`` import deferred to first-use per
ADR-0011 — the Pipeline's structural Protocol surface
(``segment(pcm) -> list[Segment]``) is unchanged so existing fakes
continue to satisfy it.

The four label tokens (``speech`` | ``music`` | ``noise`` | ``silence``)
are the contract surface the renderer (POD-011) and AC-US-2.5 / NFR-4
enforce.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol, cast

import numpy as np
import numpy.typing as npt

from .errors import ModelError

if TYPE_CHECKING:
    from collections.abc import Iterator

    class _InaEngine(Protocol):
        """Structural contract for the ``inaSpeechSegmenter.Segmenter``.

        Defined under ``TYPE_CHECKING`` so it documents the engine surface
        without importing the heavy lib (ADR-0011) — the body is a
        ``...`` stub at runtime. The real lib (v0.7.6) exposes its
        segmentation entry point as ``__call__(medianame, ...)``: a
        callable that takes a media file path and returns a list of
        ``(label, start, end)`` triples.
        """

        def __call__(
            self,
            medianame: str,
            tmpdir: str | None = None,
            start_sec: float | None = None,
            stop_sec: float | None = None,
        ) -> list[tuple[str, float, float]]: ...


SegmentLabel = Literal["speech", "music", "noise", "silence"]

_SAMPLE_RATE_HZ_DEFAULT = 16_000


@dataclass(frozen=True, slots=True)
class Segment:
    """One contiguous segmenter-labeled region of the input.

    ``start`` and ``end`` are absolute seconds in the episode timeline.
    The Pipeline iterates these in order; the renderer (POD-011) drops
    ``noise`` / ``silence`` per AC-US-2.5 and emits English markers around
    ``music`` regions per AC-US-2.2.
    """

    start: float
    end: float
    label: SegmentLabel


class Segmenter(Protocol):
    """Structural Protocol for the segmenter stage.

    POD-010 provides the ``inaSpeechSegmenter``-backed implementation;
    Tier 1 unit tests substitute a fake that returns canned segments.
    """

    def segment(self, pcm: npt.NDArray[np.float32]) -> list[Segment]:
        """Label every frame of ``pcm`` and return time-ordered segments
        covering the full duration (NFR-4 — no internal gaps).
        """
        ...


# Maps the labels emitted by ``inaSpeechSegmenter``'s ``smn`` engine
# (Speech / Music / Noise) to our four-token contract surface.
# ``noEnergy`` is the ina vocabulary for silence regions.
_INA_LABEL_MAP: dict[str, SegmentLabel] = {
    "speech": "speech",
    "music": "music",
    "noise": "noise",
    "noEnergy": "silence",
}


def _normalize_to_segments(
    raw: list[tuple[str, float, float]],
    *,
    total_duration_s: float,
) -> list[Segment]:
    """Normalize the engine's raw ``(label, start, end)`` triples.

    Maps the ina-vocabulary labels to our four-token surface, sorts by
    start time, and gap-fills with ``silence`` so the union of returned
    segments covers ``[0, total_duration_s]`` end-to-end (NFR-4).

    Raises :class:`ModelError` (exit 5) if the engine emits a label this
    mapping does not know — a known-unknown signal that the upstream lib
    has drifted (R-14 / R-17).
    """
    if total_duration_s <= 0.0:
        return []

    ordered = sorted(raw, key=lambda triple: triple[1])
    out: list[Segment] = []
    cursor = 0.0
    for label, start, end in ordered:
        if label not in _INA_LABEL_MAP:
            raise ModelError(
                f"inaSpeechSegmenter emitted an unknown label '{label}'; "
                "this is likely a library upgrade — pin or update the mapping."
            )
        if start < cursor:
            raise ModelError(
                f"inaSpeechSegmenter emitted overlapping segments "
                f"(start={start}s < previous end={cursor}s); "
                "this is upstream of NFR-3 / NFR-4 — pin or investigate the lib."
            )
        if start > cursor:
            out.append(Segment(cursor, start, "silence"))
        out.append(Segment(start, end, _INA_LABEL_MAP[label]))
        cursor = end

    if cursor < total_duration_s:
        out.append(Segment(cursor, total_duration_s, "silence"))

    return out


def to_jsonl(segments: list[Segment]) -> str:
    """Serialize ``segments`` as JSON-Lines for ``segments.jsonl``.

    POD-024 (``--debug`` artifact dir, SP-6) writes the result next to the
    input. Empty input yields an empty string; a non-empty result has one
    JSON object per line and a trailing newline.
    """
    import json

    if not segments:
        return ""
    lines = [json.dumps({"start": s.start, "end": s.end, "label": s.label}) for s in segments]
    return "\n".join(lines) + "\n"


class InaSpeechSegmenter:
    """``inaSpeechSegmenter``-backed implementation of :class:`Segmenter`.

    The heavy ``inaSpeechSegmenter`` (TensorFlow) import is deferred to
    first-use per ADR-0011 — constructing the class is cheap and does not
    touch TF.  Any ``ImportError`` from the heavy import is wrapped in
    :class:`ModelError` (exit 5) per ADR-0006 / ADR-0011 Consequences.

    ``segment()`` returns segments normalized to our four-token vocabulary
    and gap-filled with ``silence`` so every second of input is accounted
    for (NFR-4).  Ordering is non-decreasing on ``start`` (NFR-3).
    """

    def __init__(self, *, sample_rate: int = _SAMPLE_RATE_HZ_DEFAULT) -> None:
        self._sample_rate = sample_rate
        self._engine: object | None = None

    def segment(self, pcm: npt.NDArray[np.float32]) -> list[Segment]:
        if len(pcm) == 0:
            return []
        engine = self._ensure_engine()
        raw = self._run_engine(engine, pcm)
        duration_s = len(pcm) / self._sample_rate
        return _normalize_to_segments(raw, total_duration_s=duration_s)

    def _ensure_engine(self) -> object:
        """Build (and cache) the underlying engine on first call.

        Wraps :class:`ImportError` from the heavy import in
        :class:`ModelError` so the cli's exit-code translation surfaces a
        useful exit 5 instead of the unexpected-exception fallback (1).
        """
        if self._engine is None:
            try:
                self._engine = self._build_engine()
            except ImportError as e:
                raise ModelError(
                    "inaSpeechSegmenter (or its TensorFlow dependency) is not "
                    "installed — run `uv sync` to install."
                ) from e
        return self._engine

    def _build_engine(self) -> object:
        """Construct the underlying ``inaSpeechSegmenter.Segmenter``.

        Override-point for unit tests (subclass and replace this method to
        return a stub engine without touching TF).  Production code path
        triggers the lazy import here.

        Three SPK-1 compat shims fire before the heavy import (PROJECT_PLAN
        §10.1 R-1 / SRS Risk #5 — the dep-stack incompatibility the spike
        was meant to surface; we pinned dependencies to keep Apple Silicon
        viable but the lib still needs runtime patches against current TF /
        pyannote / numpy):

        1. ``TF_USE_LEGACY_KERAS=1`` — TF 2.16+ ships Keras 3 by default;
           inaSpeechSegmenter 0.7.6's bundled HDF5 model was saved under
           Keras 2 and fails to load in Keras 3 ("Invalid input shape for
           input Tensor ..."). Setting the env var routes ``tf.keras``
           through the ``tf-keras`` (Keras 2) compat package.
        2. The vendored ``pyannote.algorithms.utils.viterbi`` passes
           generators to ``np.vstack``, which numpy 2.x rejects. Patched
           in :func:`_patch_pyannote_viterbi_for_modern_numpy`.
        3. ``numpy<2`` is pinned in ``pyproject.toml`` because v0.7.6 also
           uses ``np.lib.pad`` (removed in 2.x).

        All three shims disappear the day inaSpeechSegmenter ships an
        Apple-Silicon-clean release that targets numpy 2 + Keras 3.
        """
        os.environ.setdefault("TF_USE_LEGACY_KERAS", "1")
        _patch_pyannote_viterbi_for_modern_numpy()

        from inaSpeechSegmenter import Segmenter as _InaSeg  # type: ignore[import-untyped]

        return _InaSeg(vad_engine="smn", detect_gender=False)

    def _run_engine(
        self,
        engine: object,
        pcm: npt.NDArray[np.float32],
    ) -> list[tuple[str, float, float]]:
        """Run ``engine`` on ``pcm`` and return raw ``(label, start, end)`` triples.

        Override-point for unit tests. The production implementation
        serialises ``pcm`` to a temporary WAV file (the only audio
        carrier ``inaSpeechSegmenter.Segmenter.__call__`` accepts in
        v0.7.6) and invokes the engine on its path. The temp WAV is
        deleted on context exit so a long-running process never
        accumulates fixture-sized scratch files.
        """
        real_engine = cast("_InaEngine", engine)
        with self._pcm_to_temp_wav(pcm) as wav_path:
            result = real_engine(str(wav_path))
        return [(label, float(start), float(end)) for label, start, end in result]

    @contextlib.contextmanager
    def _pcm_to_temp_wav(
        self,
        pcm: npt.NDArray[np.float32],
    ) -> Iterator[Path]:
        """Write ``pcm`` to a temp WAV (16-bit PCM) and yield its path.

        ``inaSpeechSegmenter`` re-decodes the file via its bundled
        ``ffmpeg`` wrapper; passing a 16-bit WAV at the canonical sample
        rate keeps that re-decode lossless and quick. The lib also
        accepts MP3, but WAV avoids a second encode round-trip.

        We avoid a hard ``soundfile`` / ``scipy`` runtime dep
        (ADR-0013 forbids new runtime deps) by using stdlib :mod:`wave`.
        ``pcm`` is float32 in [-1.0, 1.0] per ADR-0016; we clip and
        scale to int16 for the WAV header convention.
        """
        # Float32 → int16 for the WAV; clip first so a stray sample
        # outside [-1, 1] doesn't wrap around the int range.
        clipped = np.clip(pcm, -1.0, 1.0)
        int16 = (clipped * 32767.0).astype(np.int16)

        # Use NamedTemporaryFile so we get an OS-managed unique name,
        # but ``delete=False`` because we close the handle and then
        # hand the path to a separate process (the lib's ffmpeg).
        with tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False,
        ) as tmp:
            tmp_path = Path(tmp.name)

        try:
            with wave.open(str(tmp_path), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)  # 16-bit
                w.setframerate(self._sample_rate)
                w.writeframes(int16.tobytes())
            yield tmp_path
        finally:
            tmp_path.unlink(missing_ok=True)


_PYANNOTE_PATCHED = False


def _patch_pyannote_viterbi_for_modern_numpy() -> None:
    """SPK-1 fallback shim — see :meth:`InaSpeechSegmenter._build_engine`.

    Replaces the two functions in
    :mod:`pyannote.algorithms.utils.viterbi` that pass a generator to
    ``np.vstack`` (deprecated in numpy 1.20, hard error in 2.x) with
    list-comprehension variants. Idempotent via
    :data:`_PYANNOTE_PATCHED`. Importing pyannote here is part of the
    heavy import boundary — we already crossed it in the caller
    (``_build_engine``) so triggering it once more is free.
    """
    global _PYANNOTE_PATCHED
    if _PYANNOTE_PATCHED:
        return

    from pyannote.algorithms.utils import viterbi as _v  # type: ignore[import-untyped]

    def _update_seq(
        matrix: npt.NDArray[np.float64],
        consecutive: npt.NDArray[np.int64],
    ) -> npt.NDArray[np.float64]:
        # Materialise the generator into a list so np.vstack accepts it.
        return np.vstack(
            [np.tile(e, (c, 1)) for e, c in zip(matrix.T, consecutive, strict=False)]
        ).T

    _v._update_emission = _update_seq
    _v._update_constraint = _update_seq
    _PYANNOTE_PATCHED = True

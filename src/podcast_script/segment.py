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

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol, cast

import numpy as np
import numpy.typing as npt

from .errors import ModelError

if TYPE_CHECKING:

    class _InaEngine(Protocol):
        """Structural contract for the ``inaSpeechSegmenter`` engine.

        Defined under ``TYPE_CHECKING`` so it documents the engine surface
        without importing the heavy lib (ADR-0011) — the body is a
        ``...`` stub at runtime.
        """

        def segment_with_signal(
            self,
            signal: npt.NDArray[np.float32],
            sample_rate: int,
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
        """
        from inaSpeechSegmenter import Segmenter as _InaSeg  # type: ignore[import-untyped]

        return _InaSeg(vad_engine="smn", detect_gender=False)

    def _run_engine(
        self,
        engine: object,
        pcm: npt.NDArray[np.float32],
    ) -> list[tuple[str, float, float]]:
        """Run ``engine`` on ``pcm`` and return raw ``(label, start, end)`` triples.

        Override-point for unit tests.  The production implementation
        delegates to ``engine.segment_with_signal`` (POD-030 contract test
        verifies the ina-real-lib path; here we keep the seam thin).
        """
        # ``inaSpeechSegmenter`` consumes a (signal, sample_rate) pair via
        # its internal media reader; returns a list of (label, start, end).
        # Cast through the ``_InaEngine`` Protocol (see top of module) so
        # the structural contract is documented without forcing the heavy
        # lib's type onto the override seam.
        real_engine = cast("_InaEngine", engine)
        result = real_engine.segment_with_signal(pcm, self._sample_rate)
        return [(label, float(start), float(end)) for label, start, end in result]

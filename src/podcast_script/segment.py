"""Segmenter contracts (POD-008 seam; POD-010 fills in the impl).

The :class:`Pipeline` (POD-008) depends on the :class:`Segmenter` Protocol
and the :class:`Segment` dataclass declared here. POD-010 will add a
concrete ``InaSpeechSegmenter``-backed implementation in this same module
with the lazy TF import inside :meth:`Segmenter.load` per ADR-0011.

The four label tokens ("speech" | "music" | "noise" | "silence") are the
contract surface the renderer (POD-011) and AC-US-2.5 / NFR-4 enforce.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

import numpy as np
import numpy.typing as npt

SegmentLabel = Literal["speech", "music", "noise", "silence"]


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

    POD-010 will provide the ``InaSpeechSegmenter``-backed implementation;
    Tier 1 unit tests substitute a fake that returns canned segments.
    """

    def segment(self, pcm: npt.NDArray[np.float32]) -> list[Segment]:
        """Label every frame of ``pcm`` and return time-ordered segments
        covering the full duration (NFR-4 — no internal gaps).
        """
        ...

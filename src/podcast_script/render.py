"""Renderer contract (POD-008 seam; POD-011 fills in the impl).

POD-011 will provide a pure function :func:`render` matching this
signature, dropping ``noise`` / ``silence`` segments (AC-US-2.5), emitting
English ``music starts`` / ``music ends`` markers (AC-US-2.2), and
formatting timestamps as ``MM:SS`` < 1 h or ``HH:MM:SS`` ≥ 1 h
(AC-US-2.4 — the format is chosen by the Pipeline based on decoded
duration and passed in via ``fmt``).

Until POD-011 lands, the Pipeline accepts any callable matching
:data:`RenderFn`; tests inject a fake.
"""

from __future__ import annotations

from typing import Literal, Protocol

from .backends.base import TranscribedSegment
from .segment import Segment

TimestampFormat = Literal["MM:SS", "HH:MM:SS"]


class RenderFn(Protocol):
    """Pure-function renderer contract (POD-011)."""

    def __call__(
        self,
        segments: list[Segment],
        transcripts: list[TranscribedSegment],
        fmt: TimestampFormat,
    ) -> str:
        """Render a Markdown string for ``segments`` + ``transcripts``."""
        ...

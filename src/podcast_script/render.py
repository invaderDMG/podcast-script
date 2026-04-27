"""C-Render stage: pure Markdown emitter (POD-011).

The renderer is a pure function — given a list of :class:`Segment` (any
labels), a list of :class:`TranscribedSegment` (speech only), and a
Pipeline-chosen ``fmt``, it returns the final Markdown string. Persistence
is the Pipeline's job; logging is the Pipeline's job; this module owns
*shape* and nothing else.

Contract surface (see :class:`RenderFn`):

* AC-US-2.1 — emit ``> [<ts> — music starts]`` / ``> [<ts> — music ends]``
  blockquote markers around each ``music`` region, in time order.
* AC-US-2.2 — music marker text is **always English**, regardless of
  ``--lang``. The renderer does not see the language code.
* AC-US-2.3 — every emitted line's leading timestamp is non-decreasing
  (NFR-3 ordering invariant).
* AC-US-2.4 — every timestamp in the file uses the supplied ``fmt``;
  ``MM:SS`` for inputs < 1 h, ``HH:MM:SS`` for ≥ 1 h. The Pipeline owns
  the choice (per-file, per :func:`Pipeline._choose_fmt`); the renderer
  just applies it.
* AC-US-2.5 / NFR-4 — ``noise`` and ``silence`` segments produce no
  annotation lines; only ``speech`` text and ``music`` markers reach the
  output.
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


def render(
    segments: list[Segment],
    transcripts: list[TranscribedSegment],
    fmt: TimestampFormat,
) -> str:
    """Render the final transcript Markdown.

    Pure function — no I/O, no logging, no global state.
    """
    return ""

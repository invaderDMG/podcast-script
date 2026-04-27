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

from dataclasses import dataclass
from itertools import pairwise
from typing import Literal, Protocol

from .backends.base import TranscribedSegment
from .segment import Segment

TimestampFormat = Literal["MM:SS", "HH:MM:SS"]

_EventKind = Literal["music_start", "music_end", "speech"]

# Tie-breakers when two events share a timestamp (SRS §1.6 ordering):
# music ends first (closes the open marker), then music starts (opens
# the next), then speech text (appears at or after any markers active
# at that t). Single source of truth — keeps `_Event` to one concept
# per field.
_PRIO_BY_KIND: dict[_EventKind, int] = {
    "music_end": 0,
    "music_start": 1,
    "speech": 2,
}


@dataclass(frozen=True, slots=True)
class _Event:
    """One renderable line plus its sort key."""

    time_s: float
    kind: _EventKind
    line: str


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
    events = _build_events(segments, transcripts, fmt)
    if not events:
        return ""
    # Stable sort: ties on (time, priority) keep input order, so two
    # speech transcripts at the same start time stay in their pipeline
    # order (which is the per-segment order from ADR-0004's streaming
    # contract).
    events.sort(key=lambda e: (e.time_s, _PRIO_BY_KIND[e.kind]))
    return _join_with_block_separators(events)


def _build_events(
    segments: list[Segment],
    transcripts: list[TranscribedSegment],
    fmt: TimestampFormat,
) -> list[_Event]:
    """Materialize the renderable events from segments + transcripts.

    Drops ``noise`` and ``silence`` segments at this layer (AC-US-2.5);
    everything that survives is either a music marker or a speech line.
    """
    events: list[_Event] = []
    for seg in segments:
        if seg.label != "music":
            continue
        events.append(
            _Event(
                time_s=seg.start,
                kind="music_start",
                line=f"> [{_fmt_ts(seg.start, fmt)} — music starts]",
            )
        )
        events.append(
            _Event(
                time_s=seg.end,
                kind="music_end",
                line=f"> [{_fmt_ts(seg.end, fmt)} — music ends]",
            )
        )
    for ts in transcripts:
        events.append(
            _Event(
                time_s=ts.start,
                kind="speech",
                line=f"`{_fmt_ts(ts.start, fmt)}`  {ts.text}",
            )
        )
    return events


def _join_with_block_separators(events: list[_Event]) -> str:
    """Join lines with blank-line separators between blocks.

    A music_start → music_end pair is tight (no blank between); every
    other transition gets one blank line so the output mirrors the SRS
    §1.6 example shape.
    """
    out: list[str] = [events[0].line]
    for prev, curr in pairwise(events):
        if prev.kind == "music_start" and curr.kind == "music_end":
            out.append(curr.line)
        else:
            out.append("")
            out.append(curr.line)
    return "\n".join(out) + "\n"


def _fmt_ts(seconds: float, fmt: TimestampFormat) -> str:
    """Format ``seconds`` as ``MM:SS`` or ``HH:MM:SS`` per ``fmt``."""
    total = int(seconds)
    hh, rem = divmod(total, 3600)
    mm, ss = divmod(rem, 60)
    if fmt == "HH:MM:SS":
        return f"{hh:02d}:{mm:02d}:{ss:02d}"
    return f"{hh * 60 + mm:02d}:{ss:02d}"

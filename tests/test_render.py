"""C-Render unit tests (POD-011, ADR-0017 Tier 1).

Pure-function tests against the renderer contract: no fakes, no I/O. Each
test is named with the AC it satisfies so traceability is immediate from
the report.
"""

from __future__ import annotations

import re

from podcast_script.backends.base import TranscribedSegment
from podcast_script.render import render
from podcast_script.segment import Segment


def test_drops_noise_and_silence_segments_AC_US_2_5() -> None:
    """AC-US-2.5 / NFR-4: ``noise`` and ``silence`` segments produce no
    annotation lines. Only speech text and music markers reach the output.

    Given a segment list mixing speech, music, noise, and silence, the
    renderer's output contains no marker text near the noise/silence
    timestamps and no blockquote line referencing them.
    """
    segments = [
        Segment(0.0, 5.0, "silence"),
        Segment(5.0, 12.0, "speech"),
        Segment(12.0, 18.0, "noise"),
        Segment(18.0, 25.0, "music"),
        Segment(25.0, 30.0, "speech"),
    ]
    transcripts = [
        TranscribedSegment(start=5.0, end=12.0, text="hello world"),
        TranscribedSegment(start=25.0, end=30.0, text="and we are back"),
    ]

    out = render(segments, transcripts, "MM:SS")

    # Music markers must appear (we have one music region).
    assert "music starts" in out
    assert "music ends" in out
    # Speech text must appear.
    assert "hello world" in out
    assert "and we are back" in out
    # Neither label name leaks into the rendered Markdown for noise/silence.
    assert "noise" not in out
    assert "silence" not in out
    # The 12-second mark (noise start) and the 0-second mark (silence start)
    # must NOT carry a blockquote annotation. We assert this by checking
    # there is no ``> [`` blockquote line whose timestamp belongs to the
    # noise (12-18 s) or silence (0-5 s) windows.
    blockquote_lines = [line for line in out.splitlines() if line.startswith("> [")]
    for line in blockquote_lines:
        # Only music markers are allowed in blockquotes.
        assert "music" in line, f"unexpected blockquote: {line!r}"
    # Whitelist sanity: exactly the music start + end appear.
    music_lines = [line for line in blockquote_lines if "music" in line]
    assert len(music_lines) == 2


def test_speech_only_input_emits_no_blockquote_AC_US_2_5() -> None:
    """AC-US-2.5 corollary: with no music regions, the output has no
    blockquote lines at all — the renderer never invents markers.
    """
    segments = [Segment(0.0, 10.0, "speech")]
    transcripts = [TranscribedSegment(start=0.0, end=10.0, text="just talking")]

    out = render(segments, transcripts, "MM:SS")

    assert "just talking" in out
    assert not re.search(r"^> \[", out, flags=re.MULTILINE)
    assert "music" not in out

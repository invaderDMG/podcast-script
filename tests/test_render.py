"""C-Render unit tests (POD-011, ADR-0017 Tier 1).

Pure-function tests against the renderer contract: no fakes, no I/O. Each
test is named with the AC it satisfies so traceability is immediate from
the report.
"""

from __future__ import annotations

import re

from podcast_script.backends.base import TranscribedSegment
from podcast_script.render import TimestampFormat, render
from podcast_script.segment import Segment


def _leading_timestamps(out: str, fmt: TimestampFormat) -> list[int]:
    """Extract the leading timestamp (in seconds) from each emitted line.

    Returns one int per non-blank line carrying a timestamp. Used by the
    NFR-3 ordering assertion below.
    """
    if fmt == "HH:MM:SS":
        pattern = r"^(?:> \[|`)(\d{2}:\d{2}:\d{2})"
    else:
        pattern = r"^(?:> \[|`)(\d{2}:\d{2})"
    out_seconds: list[int] = []
    for line in out.splitlines():
        m = re.match(pattern, line)
        if m is None:
            continue
        parts = [int(p) for p in m.group(1).split(":")]
        if len(parts) == 3:
            secs = parts[0] * 3600 + parts[1] * 60 + parts[2]
        else:
            secs = parts[0] * 60 + parts[1]
        out_seconds.append(secs)
    return out_seconds


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


def test_music_marker_exact_shape_AC_US_2_1() -> None:
    """AC-US-2.1: each music region produces exactly one ``music starts``
    and one ``music ends`` blockquote line, in the SRS §1.6 shape
    ``> [<ts> — music starts]`` (em-dash U+2014, single space, square
    brackets, no trailing punctuation).
    """
    segments = [Segment(14.0, 30.0, "music")]
    transcripts: list[TranscribedSegment] = []

    out = render(segments, transcripts, "MM:SS")

    assert "> [00:14 — music starts]" in out
    assert "> [00:30 — music ends]" in out
    # Exactly one of each — never duplicate or omit.
    assert out.count("music starts") == 1
    assert out.count("music ends") == 1


def test_markers_are_english_regardless_of_speech_language_AC_US_2_2() -> None:
    """AC-US-2.2: the music marker text is always English (``music starts`` /
    ``music ends``) no matter what language the speech is in.

    The renderer signature has no ``lang`` parameter by design — the only
    way for the marker text to vary by language would be reading from
    transcript content, which the renderer must not do. We exercise this
    structurally by feeding non-English transcript text and asserting the
    English marker shape is unchanged.
    """
    segments = [
        Segment(0.0, 5.0, "music"),
        Segment(5.0, 30.0, "speech"),
    ]
    spanish_transcripts = [
        TranscribedSegment(start=5.0, end=30.0, text="Bienvenidos al podcast"),
    ]
    portuguese_transcripts = [
        TranscribedSegment(start=5.0, end=30.0, text="Bem-vindos ao podcast"),
    ]

    out_es = render(segments, spanish_transcripts, "MM:SS")
    out_pt = render(segments, portuguese_transcripts, "MM:SS")

    for out in (out_es, out_pt):
        assert "music starts" in out
        assert "music ends" in out
        # No localized variants must leak in.
        for spanish_marker in ("música empieza", "música termina", "comienza", "termina la música"):
            assert spanish_marker not in out
        for portuguese_marker in ("música começa", "música acaba", "início da música"):
            assert portuguese_marker not in out


def test_emitted_lines_are_in_non_decreasing_time_order_AC_US_2_3() -> None:
    """AC-US-2.3 / NFR-3: every emitted line's leading timestamp is
    non-decreasing.

    With music regions interspersed between speech regions, the output
    must interleave music markers and speech lines so timestamps never
    go backward. Lines of the form ``> [<ts> — music ...]`` and
    ``\\`<ts>\\`  ...`` both count toward the invariant.
    """
    segments = [
        Segment(0.0, 14.0, "music"),
        Segment(14.0, 60.0, "speech"),
        Segment(60.0, 120.0, "music"),
        Segment(120.0, 200.0, "speech"),
    ]
    transcripts = [
        TranscribedSegment(start=14.0, end=60.0, text="opening words"),
        TranscribedSegment(start=120.0, end=200.0, text="more words"),
    ]

    out = render(segments, transcripts, "MM:SS")
    timestamps = _leading_timestamps(out, "MM:SS")

    assert timestamps == sorted(timestamps), f"timestamps not non-decreasing: {timestamps}"
    # Sanity: we got the four expected leading values somewhere in the run.
    assert 0 in timestamps
    assert 14 in timestamps
    assert 60 in timestamps
    assert 120 in timestamps


def test_speech_inside_music_window_still_orders_correctly_AC_US_2_3() -> None:
    """AC-US-2.3 edge: when a speech transcript starts before a music
    region's ``ends`` marker (e.g. EC-1 music-bed-under-speech), the
    output ordering still holds — speech text at t=20 lands before
    music-ends at t=30.
    """
    segments = [
        Segment(0.0, 30.0, "music"),
        Segment(30.0, 60.0, "speech"),
    ]
    # A pathological case: speech transcript whose start lies inside the
    # music region. (Per EC-1 the segmenter could produce overlapping
    # interpretations after pipeline re-anchoring.)
    transcripts = [
        TranscribedSegment(start=20.0, end=30.0, text="under the bed"),
        TranscribedSegment(start=30.0, end=60.0, text="and now clear"),
    ]

    out = render(segments, transcripts, "MM:SS")
    timestamps = _leading_timestamps(out, "MM:SS")

    assert timestamps == sorted(timestamps)


def test_mm_ss_format_for_short_inputs_AC_US_2_4() -> None:
    """AC-US-2.4 (< 1 h branch): every timestamp uses ``MM:SS`` and
    no ``HH:`` prefix appears anywhere in the file. The Pipeline picks
    ``MM:SS`` for inputs shorter than one hour.
    """
    # ~50-minute episode: well under the 1 h cutoff.
    segments = [
        Segment(0.0, 14.0, "music"),
        Segment(14.0, 750.0, "speech"),
        Segment(750.0, 765.0, "music"),
    ]
    transcripts = [
        TranscribedSegment(start=14.0, end=750.0, text="opening"),
    ]

    out = render(segments, transcripts, "MM:SS")

    # MM:SS form present.
    assert "00:14" in out
    assert "12:30" in out  # 750 s
    assert "12:45" in out  # 765 s
    # No HH:MM:SS form anywhere — never mixes (per SRS §1.6 last paragraph).
    assert not re.search(r"\b\d{2}:\d{2}:\d{2}\b", out)


def test_hh_mm_ss_format_for_long_inputs_AC_US_2_4() -> None:
    """AC-US-2.4 (≥ 1 h branch): every timestamp uses ``HH:MM:SS`` and
    no two-digit-only ``MM:SS`` form appears.
    """
    # 1 h 42 min episode: above the 1 h cutoff.
    segments = [
        Segment(0.0, 14.0, "music"),
        Segment(14.0, 6150.0, "speech"),
        Segment(6150.0, 6162.0, "music"),
    ]
    transcripts = [
        TranscribedSegment(start=14.0, end=6150.0, text="opening"),
        TranscribedSegment(start=6162.0, end=6180.0, text="closing"),
    ]

    out = render(segments, transcripts, "HH:MM:SS")

    # HH:MM:SS form present.
    assert "00:00:14" in out
    assert "01:42:30" in out  # 6150 s
    assert "01:42:42" in out  # 6162 s
    # No bare MM:SS lines — every backticked or bracketed timestamp
    # must include the HH: prefix.
    bare_mm_ss = re.findall(r"`(\d{2}:\d{2})`", out)
    assert bare_mm_ss == [], f"unexpected bare MM:SS timestamps: {bare_mm_ss}"
    bracketed_mm_ss = re.findall(r"\[(\d{2}:\d{2}) —", out)
    assert bracketed_mm_ss == [], f"unexpected bracketed MM:SS timestamps: {bracketed_mm_ss}"


def test_multiple_music_regions_each_get_a_pair_AC_US_2_1() -> None:
    """AC-US-2.1: multiple music regions each produce their own
    start/end pair; the count matches the number of music segments.
    """
    segments = [
        Segment(0.0, 5.0, "music"),
        Segment(5.0, 60.0, "speech"),
        Segment(60.0, 75.0, "music"),
        Segment(75.0, 90.0, "speech"),
        Segment(90.0, 100.0, "music"),
    ]
    transcripts = [
        TranscribedSegment(start=5.0, end=60.0, text="middle"),
        TranscribedSegment(start=75.0, end=90.0, text="late"),
    ]

    out = render(segments, transcripts, "MM:SS")

    assert out.count("music starts") == 3
    assert out.count("music ends") == 3

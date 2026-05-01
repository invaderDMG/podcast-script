"""Property tests for the segment-merge module (POD-032).

Hypothesis-driven invariants on :func:`podcast_script.segment._normalize_to_segments`
covering NFR-3 (ordering) and NFR-4 (segmenter coverage). Backs
AC-US-2.3 (every emitted line's leading timestamp is ≥ the previous
emitted line's leading timestamp) and AC-US-2.5 (output filtering — only
``speech`` and ``music`` produce annotation lines, but the underlying
segment list MUST account for every second of input regardless).

ADR-0017 §"Property-based testing throughout" explicitly green-lights
``hypothesis`` as the Tier-2 enhancement on top of the hand-written
invariants in ``tests/test_segment.py``. The strategies here generate
the full space of *valid* raw segmenter outputs — sorted-or-not,
disjoint, label-in-known-vocabulary — because the production wrapper's
ModelError guards (overlap / unknown label) push those failure paths
into the example-based tests in ``test_segment.py``. Driving Hypothesis
into the same guard would be testing ``ModelError.__init__`` rather
than NFR-3 / NFR-4.

NFR-8 100% line coverage gate on the segment-merge surface
(``_normalize_to_segments``, ``to_jsonl``, ``Segment``) is enforced by a
discrete CI step (see ``.github/workflows/ci.yml``); these property
tests + the example tests in ``test_segment.py`` together pin the lines
that matter.
"""

from __future__ import annotations

import itertools
import json

from hypothesis import given
from hypothesis import strategies as st

from podcast_script.segment import (
    Segment,
    _normalize_to_segments,
    to_jsonl,
)

# Ina-vocabulary labels that the production mapping accepts. Drawn
# explicitly rather than via ``_INA_LABEL_MAP.keys()`` so a future
# widening of that mapping (R-14 / R-17 — upstream lib drift) triggers
# a deliberate test update rather than silently expanding the property
# coverage.
_INA_LABELS = ("speech", "music", "noise", "noEnergy")
_OUR_LABELS = frozenset({"speech", "music", "noise", "silence"})


@st.composite
def _raw_and_duration(
    draw: st.DrawFn,
) -> tuple[list[tuple[str, float, float]], float]:
    """Draw a ``(raw, total_duration_s)`` pair that satisfies the contract
    :func:`_normalize_to_segments` expects from the upstream segmenter:

    - all segments lie within ``[0, total_duration_s]``,
    - no two segments overlap,
    - each segment has ``start < end``,
    - labels come from the ina-vocabulary the mapping knows.

    The order is randomised to exercise the function's defensive sort —
    NFR-3 guards against an out-of-order engine response, so the
    property MUST hold for any permutation of a valid raw list.
    """
    n = draw(st.integers(min_value=0, max_value=8))
    # Build n disjoint intervals by drawing alternating (gap, length)
    # pairs in seconds, then accumulating. Bounded ranges keep
    # Hypothesis's budget focused on shape rather than near-overflow
    # arithmetic — the production code has no path that would overflow
    # at audio-realistic durations.
    gaps_and_lens = draw(
        st.lists(
            st.tuples(
                st.floats(
                    min_value=0.0,
                    max_value=5.0,
                    allow_nan=False,
                    allow_infinity=False,
                ),
                st.floats(
                    min_value=0.01,
                    max_value=5.0,
                    allow_nan=False,
                    allow_infinity=False,
                ),
            ),
            min_size=n,
            max_size=n,
        )
    )
    labels = draw(
        st.lists(
            st.sampled_from(_INA_LABELS),
            min_size=n,
            max_size=n,
        )
    )

    raw: list[tuple[str, float, float]] = []
    cursor = 0.0
    for label, (gap, length) in zip(labels, gaps_and_lens, strict=True):
        start = cursor + gap
        end = start + length
        raw.append((label, start, end))
        cursor = end

    # Trailing slack lets the duration extend past the last segment
    # — exercises the trailing-silence branch some of the time.
    trailing = draw(
        st.floats(
            min_value=0.0,
            max_value=5.0,
            allow_nan=False,
            allow_infinity=False,
        )
    )
    total = cursor + trailing
    raw_shuffled = draw(st.permutations(raw))
    return list(raw_shuffled), total


# ---------------------------------------------------------------------------
# NFR-3 — ordering invariant
# ---------------------------------------------------------------------------


@given(_raw_and_duration())
def test_property_NFR_3_normalize_yields_non_decreasing_starts(
    args: tuple[list[tuple[str, float, float]], float],
) -> None:
    """NFR-3 (AC-US-2.3): every emitted segment's ``start`` MUST be ≥
    the previous one's ``start``, regardless of the raw input's order.
    """
    raw, total = args
    result = _normalize_to_segments(raw, total_duration_s=total)
    starts = [s.start for s in result]
    assert starts == sorted(starts), f"non-monotonic starts: {starts}"


@given(_raw_and_duration())
def test_property_NFR_3_normalize_is_sort_idempotent(
    args: tuple[list[tuple[str, float, float]], float],
) -> None:
    """NFR-3 corollary: a defensive sort upstream of the function MUST
    produce the same output as the unsorted form. Pre-sorting in callers
    therefore can never regress NFR-3 (a property a brittle implementation
    that, say, paid attention to insertion order would violate).
    """
    raw, total = args
    pre_sorted = sorted(raw, key=lambda triple: triple[1])
    assert _normalize_to_segments(raw, total_duration_s=total) == _normalize_to_segments(
        pre_sorted, total_duration_s=total
    )


# ---------------------------------------------------------------------------
# NFR-4 — segmenter coverage invariant
# ---------------------------------------------------------------------------


@given(_raw_and_duration())
def test_property_NFR_4_normalize_covers_full_duration_without_gaps(
    args: tuple[list[tuple[str, float, float]], float],
) -> None:
    """NFR-4: every second of ``[0, total_duration_s]`` MUST be accounted
    for by exactly one segment label — no internal gaps, no overlaps,
    no leak past ``total_duration_s``.

    Empty result is permitted only when ``total_duration_s == 0``.
    """
    raw, total = args
    result = _normalize_to_segments(raw, total_duration_s=total)

    if total == 0.0:
        assert result == []
        return

    assert result, f"non-zero duration {total} produced no segments"
    assert result[0].start == 0.0, f"first segment must start at 0; got {result[0].start}"
    assert result[-1].end == total, (
        f"last segment must end at total_duration_s={total}; got {result[-1].end}"
    )
    for prev, curr in itertools.pairwise(result):
        assert curr.start == prev.end, (
            f"gap or overlap between {prev} and {curr}: {prev.end} != {curr.start}"
        )


@given(_raw_and_duration())
def test_property_NFR_4_labels_are_in_four_token_vocabulary(
    args: tuple[list[tuple[str, float, float]], float],
) -> None:
    """NFR-4 vocabulary side: every emitted label MUST be one of the four
    contract tokens. The renderer (POD-011 / AC-US-2.5) relies on this
    closed set when deciding which segments produce annotation lines.
    """
    raw, total = args
    result = _normalize_to_segments(raw, total_duration_s=total)
    labels = {s.label for s in result}
    assert labels <= _OUR_LABELS, f"unexpected label leaked: {labels - _OUR_LABELS}"


@given(_raw_and_duration())
def test_property_normalize_segments_have_strictly_positive_length(
    args: tuple[list[tuple[str, float, float]], float],
) -> None:
    """A zero-length segment would corrupt downstream timestamp ordering
    in a way NFR-3's non-decreasing relation can't detect — assert the
    stronger invariant that every emitted segment occupies real time.
    """
    raw, total = args
    result = _normalize_to_segments(raw, total_duration_s=total)
    for seg in result:
        assert seg.end > seg.start, f"non-positive-length segment: {seg}"


# ---------------------------------------------------------------------------
# to_jsonl serialiser — round-trip invariant
# ---------------------------------------------------------------------------


@given(_raw_and_duration())
def test_property_to_jsonl_roundtrips_each_segment(
    args: tuple[list[tuple[str, float, float]], float],
) -> None:
    """Each line of ``to_jsonl(segments)`` MUST parse back to the same
    ``(start, end, label)`` triple — the wire format POD-024's
    ``--debug`` artifact dir relies on.
    """
    raw, total = args
    segments = _normalize_to_segments(raw, total_duration_s=total)
    text = to_jsonl(segments)

    if not segments:
        assert text == ""
        return

    lines = text.rstrip("\n").split("\n")
    assert len(lines) == len(segments)
    for line, seg in zip(lines, segments, strict=True):
        parsed = json.loads(line)
        assert parsed == {"start": seg.start, "end": seg.end, "label": seg.label}


# ---------------------------------------------------------------------------
# Segment dataclass — frozen immutability sanity check
# ---------------------------------------------------------------------------


def test_segment_dataclass_is_frozen() -> None:
    """``Segment`` is declared ``frozen=True`` so the segment list passed
    around the pipeline can't be mutated in flight. Pin that here so a
    refactor that drops ``frozen`` shows up as a test break rather than
    a subtle ordering bug downstream.
    """
    seg = Segment(0.0, 1.0, "speech")
    try:
        seg.start = 99.0  # type: ignore[misc]
    except (AttributeError, TypeError):
        return
    raise AssertionError("Segment should be frozen — start was mutable")

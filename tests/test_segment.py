"""Tests for the C-Segment stage (POD-010).

Tier 1 unit tests per ADR-0017: pure label-normalization logic and the
``InaSpeechSegmenter`` wrapper exercised against a mocked engine seam.
The real ``inaSpeechSegmenter`` (TF-backed) is not imported here — the
lazy-import boundary (ADR-0011) is verified via a monkey-patched seam,
not by actually loading TF.

The Tier 2 contract test against the real library lands with POD-030
(SP-4/SP-6); the Tier 3 full-pipeline integration arrives with POD-031
(SP-7).
"""

from __future__ import annotations

import json

import numpy as np
import numpy.typing as npt
import pytest

from podcast_script.errors import ModelError
from podcast_script.segment import (
    InaSpeechSegmenter,
    Segment,
    _normalize_to_segments,
    to_jsonl,
)

SAMPLE_RATE = 16_000


def _silence_pcm(duration_s: float) -> npt.NDArray[np.float32]:
    return np.zeros(int(duration_s * SAMPLE_RATE), dtype=np.float32)


# ---------------------------------------------------------------------------
# _normalize_to_segments — pure logic
# ---------------------------------------------------------------------------


def test_normalize_maps_ina_labels_to_four_token_vocabulary() -> None:
    """Ina's ``smn`` engine emits {speech, music, noise, noEnergy}; we
    normalize to the contract surface {speech, music, noise, silence}.
    """
    raw = [
        ("speech", 0.0, 1.0),
        ("music", 1.0, 2.0),
        ("noise", 2.0, 3.0),
        ("noEnergy", 3.0, 4.0),
    ]
    result = _normalize_to_segments(raw, total_duration_s=4.0)

    assert [s.label for s in result] == ["speech", "music", "noise", "silence"]


def test_normalize_fills_gaps_with_silence_NFR_4() -> None:
    """NFR-4: every second of input MUST be accounted for by exactly one
    segment label — internal gaps in the raw output are filled with
    ``silence``.
    """
    raw = [("speech", 1.0, 3.0), ("music", 5.0, 7.0)]
    result = _normalize_to_segments(raw, total_duration_s=10.0)

    assert result == [
        Segment(0.0, 1.0, "silence"),
        Segment(1.0, 3.0, "speech"),
        Segment(3.0, 5.0, "silence"),
        Segment(5.0, 7.0, "music"),
        Segment(7.0, 10.0, "silence"),
    ]


def test_normalize_empty_raw_yields_single_silence_segment() -> None:
    """An empty raw segmentation (engine returned nothing) MUST still
    cover ``[0, total_duration_s]`` per NFR-4 — fall back to ``silence``.
    """
    result = _normalize_to_segments([], total_duration_s=5.0)

    assert result == [Segment(0.0, 5.0, "silence")]


def test_normalize_zero_duration_yields_empty_list() -> None:
    """A zero-length input has nothing to cover."""
    result = _normalize_to_segments([], total_duration_s=0.0)

    assert result == []


def test_normalize_sorts_unordered_raw_NFR_3() -> None:
    """NFR-3 ordering invariant: if the engine returns segments out of
    order (defensive), the normalized output is still time-ordered.
    """
    raw = [("music", 5.0, 7.0), ("speech", 1.0, 3.0)]
    result = _normalize_to_segments(raw, total_duration_s=10.0)

    starts = [s.start for s in result]
    assert starts == sorted(starts)


def test_normalize_unknown_label_raises_model_error() -> None:
    """An ina-library upgrade that introduces a new label token is a
    known-unknown (R-14 / R-17): surface as ``ModelError`` (exit 5) rather
    than silently mapping to ``silence`` and corrupting the transcript.
    """
    raw = [("brand_new_label_v2", 0.0, 1.0)]
    with pytest.raises(ModelError, match="brand_new_label_v2"):
        _normalize_to_segments(raw, total_duration_s=1.0)


def test_normalize_overlapping_segments_raises_model_error() -> None:
    """``inaSpeechSegmenter``'s frame-classifier produces non-overlapping
    segments by design; if the engine ever returns overlapping regions,
    that's the same library-drift signal as an unknown label (R-14 /
    R-17). Loud-fail with :class:`ModelError` rather than silently
    clamp — a corrupted segmentation is upstream of every downstream
    invariant (NFR-3 / NFR-4) and should surface immediately.
    """
    raw = [("speech", 0.0, 5.0), ("music", 3.0, 7.0)]
    with pytest.raises(ModelError, match="overlapping"):
        _normalize_to_segments(raw, total_duration_s=10.0)


def test_normalize_no_gap_when_segments_already_cover_full_duration() -> None:
    """When raw already covers ``[0, total_duration_s]`` end-to-end, no
    silence padding is inserted (contiguity is preserved).
    """
    raw = [("speech", 0.0, 2.0), ("music", 2.0, 5.0)]
    result = _normalize_to_segments(raw, total_duration_s=5.0)

    assert result == [
        Segment(0.0, 2.0, "speech"),
        Segment(2.0, 5.0, "music"),
    ]


# ---------------------------------------------------------------------------
# InaSpeechSegmenter — happy path with mocked engine seam
# ---------------------------------------------------------------------------


class _StubInaSegmenter(InaSpeechSegmenter):
    """Subclass that bypasses the real lazy import / engine construction.

    Exposes ``raw_to_return`` for the engine output and counters for the
    import + build hooks, so we can test caching and import-failure
    propagation without ever touching TensorFlow.
    """

    def __init__(
        self,
        raw_to_return: list[tuple[str, float, float]],
        *,
        sample_rate: int = SAMPLE_RATE,
        import_error: Exception | None = None,
    ) -> None:
        super().__init__(sample_rate=sample_rate)
        self._raw = raw_to_return
        self._import_error = import_error
        self.import_calls = 0
        self.engine_runs = 0

    def _build_engine(self) -> object:
        self.import_calls += 1
        if self._import_error is not None:
            raise self._import_error
        return object()  # opaque sentinel — _run_engine ignores it

    def _run_engine(
        self,
        engine: object,
        pcm: npt.NDArray[np.float32],
    ) -> list[tuple[str, float, float]]:
        self.engine_runs += 1
        return list(self._raw)


def test_segment_returns_normalized_full_coverage() -> None:
    """``segment()`` returns time-ordered, gap-filled segments covering
    the full PCM duration computed from ``len(pcm) / sample_rate``.
    """
    pcm = _silence_pcm(4.0)
    segmenter = _StubInaSegmenter(
        raw_to_return=[("speech", 1.0, 3.0)],
    )

    result = segmenter.segment(pcm)

    assert result == [
        Segment(0.0, 1.0, "silence"),
        Segment(1.0, 3.0, "speech"),
        Segment(3.0, 4.0, "silence"),
    ]


def test_segment_zero_length_pcm_returns_empty_list() -> None:
    """Edge case: a zero-length PCM yields no segments without crashing
    (the orchestrator guards against this earlier, but defense in depth).
    """
    pcm = _silence_pcm(0.0)
    segmenter = _StubInaSegmenter(raw_to_return=[])

    assert segmenter.segment(pcm) == []


# ---------------------------------------------------------------------------
# Engine caching across calls (ADR-0011 first-use site)
# ---------------------------------------------------------------------------


def test_engine_built_lazily_once_and_reused() -> None:
    """ADR-0011: the heavy import happens at first-use, not at construction.
    A second ``segment()`` call MUST NOT trigger a second import/build.
    """
    pcm = _silence_pcm(1.0)
    segmenter = _StubInaSegmenter(raw_to_return=[("speech", 0.0, 1.0)])

    # No import at construction.
    assert segmenter.import_calls == 0

    segmenter.segment(pcm)
    assert segmenter.import_calls == 1
    assert segmenter.engine_runs == 1

    segmenter.segment(pcm)
    assert segmenter.import_calls == 1  # unchanged — engine is cached
    assert segmenter.engine_runs == 2


def test_segment_module_does_not_eagerly_import_inaspeechsegmenter() -> None:
    """ADR-0011: ``segment.py`` MUST NOT import ``inaSpeechSegmenter`` at
    module top — that would defeat the cold-start budget for ``--help``
    and the validation paths, and would surface install conflicts before
    any user-actionable context is logged.

    Companion regression to ``test_engine_built_lazily_once_and_reused``:
    the latter verifies the *class-level* lazy boundary via the override
    seam, but would still pass if a future edit moved the import to the
    module top. This test guards the *module-level* boundary.
    """
    import importlib
    import sys

    sys.modules.pop("podcast_script.segment", None)
    sys.modules.pop("inaSpeechSegmenter", None)

    importlib.import_module("podcast_script.segment")

    assert "inaSpeechSegmenter" not in sys.modules


# ---------------------------------------------------------------------------
# ImportError → ModelError wrap (ADR-0006 + ADR-0011 Consequences)
# ---------------------------------------------------------------------------


def test_import_error_is_wrapped_in_model_error() -> None:
    """ADR-0011 Consequences: an `ImportError` from the heavy lib MUST be
    wrapped in :class:`ModelError` (exit 5) so the cli can map it to the
    NFR-9 exit-code contract instead of falling out as exit 1.
    """
    pcm = _silence_pcm(1.0)
    segmenter = _StubInaSegmenter(
        raw_to_return=[],
        import_error=ImportError("No module named 'inaSpeechSegmenter'"),
    )

    with pytest.raises(ModelError) as exc_info:
        segmenter.segment(pcm)

    assert isinstance(exc_info.value.__cause__, ImportError)


# ---------------------------------------------------------------------------
# to_jsonl serializer (POD-024 will consume this)
# ---------------------------------------------------------------------------


def test_to_jsonl_emits_one_object_per_segment() -> None:
    """``to_jsonl`` is the wire format POD-024 (`--debug` artifact dir) will
    write to ``<input-stem>.debug/segments.jsonl``. One JSON object per
    line, keys ``start`` / ``end`` / ``label``, trailing newline.
    """
    segments = [
        Segment(0.0, 1.5, "silence"),
        Segment(1.5, 3.0, "speech"),
    ]
    text = to_jsonl(segments)

    lines = text.rstrip("\n").split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"start": 0.0, "end": 1.5, "label": "silence"}
    assert json.loads(lines[1]) == {"start": 1.5, "end": 3.0, "label": "speech"}
    assert text.endswith("\n")


def test_to_jsonl_empty_list_yields_empty_string() -> None:
    """No segments → empty output (POD-024 may still write the file)."""
    assert to_jsonl([]) == ""

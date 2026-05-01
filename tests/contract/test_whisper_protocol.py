"""Tier 2 contract tests for the WhisperBackend Protocol (POD-030).

Each invariant runs against every backend in the parametrized
``backend_factory`` fixture from :mod:`tests.contract.conftest` —
``FakeBackend`` (always) plus each real backend whose library is
importable on the current host. The same ``test_*`` function shape
catches "the fake is no longer behaving like the real thing" drift
that a fake-only Tier 1 suite is blind to (ADR-0017).
"""

from __future__ import annotations

from itertools import pairwise

import numpy as np
import numpy.typing as npt
import pytest

from podcast_script.backends.base import TranscribedSegment
from tests.contract.conftest import BackendFactory

SAMPLE_RATE = 16_000


def _silence_pcm(duration_s: float) -> npt.NDArray[np.float32]:
    """Generate ``duration_s`` of silence (zeros) at the project sample rate."""
    return np.zeros(int(duration_s * SAMPLE_RATE), dtype=np.float32)


# ---------------------------------------------------------------------------
# I1 — empty PCM yields an empty Iterable without raising
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_transcribe_empty_pcm_yields_empty_iterable(
    backend_factory: BackendFactory,
) -> None:
    """ADR-0017 Tier 2 invariant I1: ``transcribe(empty_pcm, lang)`` MUST
    return an Iterable that produces zero items, without raising. The
    pipeline (POD-008) feeds one speech segment at a time — a
    zero-length speech segment (rare but legal — segmenter coalesces
    near-zero-duration regions into noise) must not crash the run.

    A backend that materialises ``pcm`` into a model call without an
    early-return guard would either raise (numpy zero-shape -> lib
    error) or silently emit a hallucinated transcript — both are
    contract violations.
    """
    backend = backend_factory()
    empty = np.zeros(0, dtype=np.float32)

    result = list(backend.transcribe(empty, lang="es"))

    assert result == []
    for seg in result:
        assert isinstance(seg, TranscribedSegment)


# ---------------------------------------------------------------------------
# I2 — silence PCM does not raise (yielding empty or zero-text is fine)
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_transcribe_silence_does_not_raise(
    backend_factory: BackendFactory,
) -> None:
    """ADR-0017 Tier 2 invariant I2: ``transcribe(silence_pcm, lang)``
    MUST NOT raise. Real episodes routinely contain silent intros /
    outros / inter-segment gaps; the segmenter (C-Segment) carves them
    out as ``noise`` / ``silence`` regions which the renderer drops, but
    short residual silent slices still reach the backend. A backend
    that explodes on near-zero-variance input (z-score normalisation
    inside whisper-class models is a known offender) would fail every
    real run.

    The contract permits either an empty Iterable or zero-text segments
    — both are acceptable per ADR-0017. We only assert the absence of
    an exception, and that any yielded items are well-typed.
    """
    backend = backend_factory()
    silence = _silence_pcm(2.0)

    out = list(backend.transcribe(silence, lang="es"))

    for seg in out:
        assert isinstance(seg, TranscribedSegment)


# ---------------------------------------------------------------------------
# I3 — yielded segment starts are non-decreasing within a single call
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_transcribe_yields_non_decreasing_starts(
    backend_factory: BackendFactory,
) -> None:
    """ADR-0017 Tier 2 invariant I3: within a single ``transcribe`` call
    the yielded ``TranscribedSegment.start`` values MUST be
    non-decreasing. The renderer (POD-011) interleaves speech with
    music markers by absolute time and assumes monotonic ordering — an
    out-of-order yield would produce a Markdown timeline that contradicts
    itself.

    Real backends produce monotonic output naturally (Whisper decoders
    walk the audio left-to-right). The fake's :data:`_DEFAULT_CANNED`
    is also monotonic; mutation-tested locally by reversing the canned
    list — the assertion below catches the regression.
    """
    backend = backend_factory()
    pcm = _silence_pcm(3.0)

    starts = [seg.start for seg in backend.transcribe(pcm, lang="es")]

    for prev, nxt in pairwise(starts):
        assert prev <= nxt, (
            f"non-decreasing-start invariant violated: {prev} > {nxt} in sequence {starts}"
        )


# ---------------------------------------------------------------------------
# I4 — transcribe is callable repeatedly on the same instance after load()
# ---------------------------------------------------------------------------


@pytest.mark.contract
def test_transcribe_is_repeatable_after_single_load(
    backend_factory: BackendFactory,
) -> None:
    """ADR-0017 Tier 2 invariant I4: a single backend instance MUST
    accept multiple ``transcribe`` calls after one ``load`` call. The
    Pipeline (POD-008) iterates the segmenter's speech regions and
    invokes ``transcribe`` once per region per ADR-0004's streaming
    contract; if a backend turned single-use after the first call, an
    episode with two speech segments would fail on the second.

    Implicit single-use state would manifest as either a raised
    exception on the second call or a silently-empty result. We assert
    the call **completes** (the result may legally be empty for silence
    inputs per I2) and that no exception escapes.
    """
    backend = backend_factory()
    pcm = _silence_pcm(1.5)

    list(backend.transcribe(pcm, lang="es"))
    list(backend.transcribe(pcm, lang="es"))

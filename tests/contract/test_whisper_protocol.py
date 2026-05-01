"""Tier 2 contract tests for the WhisperBackend Protocol (POD-030).

Each invariant runs against every backend in the parametrized
``backend_factory`` fixture from :mod:`tests.contract.conftest` —
``FakeBackend`` (always) plus each real backend whose library is
importable on the current host. The same ``test_*`` function shape
catches "the fake is no longer behaving like the real thing" drift
that a fake-only Tier 1 suite is blind to (ADR-0017).
"""

from __future__ import annotations

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

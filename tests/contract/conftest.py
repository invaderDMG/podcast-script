"""Parametrized backend fixture for Tier 2 contract tests (POD-030).

Each contract test receives a ``backend_factory`` callable that returns
a freshly :meth:`~podcast_script.backends.base.WhisperBackend.load`-ed
instance, parametrized over ``FakeBackend`` plus each real backend
whose library is importable on the current host. The skip-on-ImportError
gate per ADR-0011 keeps the suite runnable on a Linux dev machine
without ``mlx_whisper`` installed; CI runs the Ubuntu + macOS-14 matrix
where both libs are present.

Real backends use ``--model tiny`` per ADR-0017 §Tier 2 to keep wall
time tractable (~10-30 s per test on a cold cache; near-instant once
the HF cache is warm). The factory returns the backend already loaded
so individual tests stay focused on the ``transcribe`` contract.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Callable

import pytest

from podcast_script.backends.base import WhisperBackend
from tests.fakes.whisper import FakeBackend

BackendFactory = Callable[[], WhisperBackend]

_FASTER_TINY_MODEL = "tiny"
# mlx-whisper expects a full HF repo ID — bare ``"tiny"`` 404s. The
# sibling ``_is_cached`` anchors on the ``/whisper-{model}`` convention
# but ``_build_model`` does not normalise; tracked as a follow-up in
# .task/POD-030.md (out of POD-030 scope; this is a US-5 bug).
_MLX_TINY_MODEL = "mlx-community/whisper-tiny"
_REAL_DEVICE = "cpu"


def _fake_backend_factory() -> WhisperBackend:
    """Build a default-configured FakeBackend with two canned segments.

    Two segments (rather than one) exercise the multi-yield path through
    :meth:`WhisperBackend.transcribe`; the start values are
    non-decreasing so invariant I3 has a default-pass case for the
    silence / arbitrary-PCM tests that don't override the fake's
    canned data.
    """
    from podcast_script.backends.base import TranscribedSegment

    backend = FakeBackend(
        canned=[
            TranscribedSegment(start=0.0, end=1.5, text="hola"),
            TranscribedSegment(start=1.5, end=3.0, text="qué tal"),
        ],
    )
    backend.load(model="fake-tiny", device="cpu")
    return backend


def _faster_backend_factory() -> WhisperBackend:
    from podcast_script.backends.faster import FasterWhisperBackend

    backend = FasterWhisperBackend()
    backend.load(model=_FASTER_TINY_MODEL, device=_REAL_DEVICE)
    return backend


def _mlx_backend_factory() -> WhisperBackend:
    from podcast_script.backends.mlx import MlxWhisperBackend

    backend = MlxWhisperBackend()
    backend.load(model=_MLX_TINY_MODEL, device=_REAL_DEVICE)
    return backend


def _backend_params() -> list[object]:
    """Build the parametrization list, skipping real backends on ImportError.

    ``importlib.util.find_spec`` is the cheap probe — it does not import
    the heavy library, just checks installability. Real-backend params
    carry ``pytest.mark.skip`` reasons that name the missing dep so the
    skip output points the developer at the fix.
    """
    params: list[object] = [
        pytest.param(_fake_backend_factory, id="fake-whisper"),
    ]

    if importlib.util.find_spec("faster_whisper") is not None:
        params.append(pytest.param(_faster_backend_factory, id="faster-whisper"))
    else:
        params.append(
            pytest.param(
                _faster_backend_factory,
                id="faster-whisper",
                marks=pytest.mark.skip(reason="faster_whisper not importable"),
            )
        )

    if importlib.util.find_spec("mlx_whisper") is not None:
        params.append(pytest.param(_mlx_backend_factory, id="mlx-whisper"))
    else:
        params.append(
            pytest.param(
                _mlx_backend_factory,
                id="mlx-whisper",
                marks=pytest.mark.skip(reason="mlx_whisper not importable"),
            )
        )

    return params


@pytest.fixture(params=_backend_params())
def backend_factory(request: pytest.FixtureRequest) -> BackendFactory:
    """Return a callable building one freshly-loaded backend per call.

    Tests that need multiple instances (e.g. invariant I4 — repeatable
    transcribe across calls on a single instance) call the factory
    once; tests that need a fresh instance per assertion call it again.
    The fixture is parametrized at the function level — each test runs
    once per backend in :func:`_backend_params`.
    """
    factory: BackendFactory = request.param
    return factory

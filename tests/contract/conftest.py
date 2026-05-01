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
FailingBackendFactory = Callable[[BaseException], WhisperBackend]
CacheMissBackendFactory = Callable[[float], WhisperBackend]

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


# ---------------------------------------------------------------------------
# Failing-load fixture (invariant I5)
# ---------------------------------------------------------------------------


def _failing_fake_factory(failure: BaseException) -> WhisperBackend:
    return FakeBackend(load_failure=failure)


def _failing_faster_factory(failure: BaseException) -> WhisperBackend:
    """Return a faster-whisper backend whose ``_build_model`` raises ``failure``.

    Uses the same override seam Tier 1 unit tests use (POD-019). The
    contract under test is the wrap inside :meth:`load` that turns any
    underlying failure into :class:`ModelError`; the seam keeps us off
    the real network and CTranslate2 chain while still exercising the
    production ``except Exception`` branch.
    """
    from podcast_script.backends.faster import FasterWhisperBackend

    class _FailingFaster(FasterWhisperBackend):
        def _build_model(self, model: str, device: str) -> object:
            raise failure

    return _FailingFaster()


def _failing_mlx_factory(failure: BaseException) -> WhisperBackend:
    """Mirror of ``_failing_faster_factory`` for the mlx backend."""
    from podcast_script.backends.mlx import MlxWhisperBackend

    class _FailingMlx(MlxWhisperBackend):
        def _build_model(self, model: str, device: str) -> object:
            raise failure

    return _FailingMlx()


def _failing_backend_params() -> list[object]:
    """Per-backend factories that take a failure exception and yield a
    backend whose ``load()`` will raise that exception through the
    underlying seam. Skip-on-ImportError matches :func:`_backend_params`
    so the matrix shape is identical.
    """
    params: list[object] = [
        pytest.param(_failing_fake_factory, id="fake-whisper"),
    ]
    if importlib.util.find_spec("faster_whisper") is not None:
        params.append(pytest.param(_failing_faster_factory, id="faster-whisper"))
    else:
        params.append(
            pytest.param(
                _failing_faster_factory,
                id="faster-whisper",
                marks=pytest.mark.skip(reason="faster_whisper not importable"),
            )
        )
    if importlib.util.find_spec("mlx_whisper") is not None:
        params.append(pytest.param(_failing_mlx_factory, id="mlx-whisper"))
    else:
        params.append(
            pytest.param(
                _failing_mlx_factory,
                id="mlx-whisper",
                marks=pytest.mark.skip(reason="mlx_whisper not importable"),
            )
        )
    return params


@pytest.fixture(params=_failing_backend_params())
def failing_backend_factory(request: pytest.FixtureRequest) -> FailingBackendFactory:
    """Return a callable that builds a backend pre-wired to fail on load.

    The caller passes the failure exception (e.g.
    ``ConnectionError("boom")`` for AC-US-5.4-shaped scenarios); the
    factory routes through each backend's load-time seam so the
    ``except Exception`` wrap inside :meth:`load` is the code path
    actually exercised. The Tier 2 contract is "every backend
    surfaces this as :class:`ModelError`, never as the raw exception".
    """
    factory: FailingBackendFactory = request.param
    return factory


# ---------------------------------------------------------------------------
# Synthetic cache-miss fixture (R-14 — first-run notice within 1 s)
# ---------------------------------------------------------------------------


def _cache_miss_fake_factory(build_delay_s: float) -> WhisperBackend:
    return FakeBackend(cache_miss=True, load_delay_s=build_delay_s)


def _cache_miss_faster_factory(build_delay_s: float) -> WhisperBackend:
    """faster-whisper backend with synthetic cache miss + slow build.

    Overrides ``_is_cached`` to ``False`` (forces the notice path) and
    inserts ``build_delay_s`` of sleep inside ``_build_model`` so the
    R-14 contract test can verify the notice fires BEFORE the slow
    network/disk path — the production code path is the same wrap +
    helper-call ordering inside :meth:`load`.
    """
    import time as _time

    from podcast_script.backends.faster import FasterWhisperBackend

    class _CacheMissFaster(FasterWhisperBackend):
        def _is_cached(self, model: str) -> bool:
            return False

        def _build_model(self, model: str, device: str) -> object:
            if build_delay_s > 0:
                _time.sleep(build_delay_s)
            return object()

    return _CacheMissFaster()


def _cache_miss_mlx_factory(build_delay_s: float) -> WhisperBackend:
    """Mirror of ``_cache_miss_faster_factory`` for the mlx backend."""
    import time as _time

    from podcast_script.backends.mlx import MlxWhisperBackend

    class _CacheMissMlx(MlxWhisperBackend):
        def _is_cached(self, model: str) -> bool:
            return False

        def _build_model(self, model: str, device: str) -> object:
            if build_delay_s > 0:
                _time.sleep(build_delay_s)
            return object()

    return _CacheMissMlx()


def _cache_miss_backend_params() -> list[object]:
    params: list[object] = [
        pytest.param(_cache_miss_fake_factory, id="fake-whisper"),
    ]
    if importlib.util.find_spec("faster_whisper") is not None:
        params.append(pytest.param(_cache_miss_faster_factory, id="faster-whisper"))
    else:
        params.append(
            pytest.param(
                _cache_miss_faster_factory,
                id="faster-whisper",
                marks=pytest.mark.skip(reason="faster_whisper not importable"),
            )
        )
    if importlib.util.find_spec("mlx_whisper") is not None:
        params.append(pytest.param(_cache_miss_mlx_factory, id="mlx-whisper"))
    else:
        params.append(
            pytest.param(
                _cache_miss_mlx_factory,
                id="mlx-whisper",
                marks=pytest.mark.skip(reason="mlx_whisper not importable"),
            )
        )
    return params


@pytest.fixture(params=_cache_miss_backend_params())
def cache_miss_backend_factory(
    request: pytest.FixtureRequest,
) -> CacheMissBackendFactory:
    """Return a callable that builds a backend with a synthetic cache miss.

    The caller passes a ``build_delay_s`` (seconds) which is the
    artificial delay inserted inside ``_build_model`` to simulate a
    slow HF download. The R-14 contract test passes a delay long
    enough to demonstrate the notice fires BEFORE the slow part —
    short enough to keep the suite quick.
    """
    factory: CacheMissBackendFactory = request.param
    return factory

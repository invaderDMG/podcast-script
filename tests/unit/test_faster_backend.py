"""Tests for the C-FasterWhisper backend (POD-019, POD-021).

Tier 1 unit tests per ADR-0017: the lazy-import boundary (ADR-0011),
the ``ImportError`` → :class:`ModelError` wrap (ADR-0006), the
``transcribe()`` shape (ADR-0003 / ADR-0004), and the AC-US-5.1
first-run model-download notice (POD-021) exercised against a mocked
cache-detection seam. The real ``faster_whisper`` is never imported
in this suite — POD-030 (SP-6) lands the Tier 2 contract test that
runs against the actual library.
"""

from __future__ import annotations

import importlib
import logging
import sys
import types
from collections.abc import Iterable, Iterator
from typing import Any

import numpy as np
import numpy.typing as npt
import pytest

from podcast_script.backends.base import TranscribedSegment
from podcast_script.backends.faster import FasterWhisperBackend
from podcast_script.errors import ModelError

SAMPLE_RATE = 16_000


def _silence_pcm(duration_s: float) -> npt.NDArray[np.float32]:
    return np.zeros(int(duration_s * SAMPLE_RATE), dtype=np.float32)


# ---------------------------------------------------------------------------
# ADR-0011 — module-level lazy-import boundary
# ---------------------------------------------------------------------------


def test_module_does_not_eagerly_import_faster_whisper() -> None:
    """ADR-0011: ``backends/faster.py`` MUST NOT import ``faster_whisper``
    at module top — the heavy CTranslate2 / tokenizers chain is deferred
    to first-use inside :meth:`FasterWhisperBackend.load`. Importing the
    module (e.g. for ``select_backend`` resolution at CLI startup) must
    not trigger the cold-import cost.
    """
    sys.modules.pop("podcast_script.backends.faster", None)
    sys.modules.pop("faster_whisper", None)

    importlib.import_module("podcast_script.backends.faster")

    assert "faster_whisper" not in sys.modules


def test_constructor_does_not_import_faster_whisper() -> None:
    """ADR-0011: instantiating the backend MUST be cheap — the heavy
    library is loaded only when :meth:`load` is called. Companion to the
    module-level test: this guards the *class-construction* boundary.
    """
    sys.modules.pop("faster_whisper", None)

    from podcast_script.backends.faster import FasterWhisperBackend

    backend = FasterWhisperBackend()

    assert backend.name == "faster-whisper"
    assert "faster_whisper" not in sys.modules


# ---------------------------------------------------------------------------
# ADR-0006 / ADR-0011 Consequences — ImportError wrap inside load()
# ---------------------------------------------------------------------------


def _make_backend_with_build_error(error: Exception) -> FasterWhisperBackend:
    """Build a backend whose ``_build_model`` raises ``error`` on load.

    Helper kept here (rather than in conftest) because no other test file
    needs it; POD-030 (Tier 2 contract) tests will run against the real
    backend, not via this seam.
    """

    class _ErrorBackend(FasterWhisperBackend):
        def _build_model(self, model: str, device: str) -> object:
            raise error

    return _ErrorBackend()


def test_load_wraps_import_error_in_model_error() -> None:
    """ADR-0011 Consequences: an ``ImportError`` from the heavy chain
    (CTranslate2 / tokenizers / faster_whisper itself) MUST surface as
    :class:`ModelError` (exit 5) so ``cli.py``'s NFR-9 mapping translates
    it to the published exit-code contract instead of the unexpected
    fallback (exit 1).
    """
    backend = _make_backend_with_build_error(
        ImportError("No module named 'faster_whisper'"),
    )

    with pytest.raises(ModelError) as exc_info:
        backend.load(model="tiny", device="cpu")

    assert isinstance(exc_info.value.__cause__, ImportError)
    assert "faster-whisper" in str(exc_info.value)


def test_load_caches_model_across_calls() -> None:
    """ADR-0011 first-use site: a second :meth:`load` call MUST NOT
    re-invoke the heavy build path. The Pipeline calls ``load()`` once
    per run today (ADR-0009), but in-process re-use (e.g. a future batch
    mode) must not pay the cost twice.
    """
    build_calls = 0

    class _CountingBackend(FasterWhisperBackend):
        def _build_model(self, model: str, device: str) -> object:
            nonlocal build_calls
            build_calls += 1
            return object()

    backend = _CountingBackend()
    backend.load(model="tiny", device="cpu")
    backend.load(model="tiny", device="cpu")

    assert build_calls == 1


# ---------------------------------------------------------------------------
# ADR-0003 / ADR-0004 — transcribe() shape (Iterable[TranscribedSegment])
# ---------------------------------------------------------------------------


class _FakeFasterSegment:
    """Stand-in for a ``faster_whisper`` segment object.

    The real lib emits objects with ``.start``, ``.end``, ``.text``
    attributes; this minimal duck-type captures that surface so the unit
    test can drive ``transcribe()`` without importing CTranslate2.
    """

    def __init__(self, start: float, end: float, text: str) -> None:
        self.start = start
        self.end = end
        self.text = text


def _make_backend_with_canned_segments(
    segments: list[_FakeFasterSegment],
) -> FasterWhisperBackend:
    """Build a backend whose loaded ``_model`` returns ``segments``.

    Mirrors how ``faster_whisper.WhisperModel.transcribe`` returns
    ``(segments_iter, info)`` — the seam is the ``_run_inference`` hook
    so unit tests don't depend on the lib's API shape.
    """

    class _CannedBackend(FasterWhisperBackend):
        def _build_model(self, model: str, device: str) -> object:
            return object()  # opaque sentinel — _run_inference ignores it

        def _run_inference(
            self,
            model: object,
            pcm: npt.NDArray[np.float32],
            lang: str,
        ) -> Iterable[_FakeFasterSegment]:
            return iter(segments)

    backend = _CannedBackend()
    backend.load(model="tiny", device="cpu")
    return backend


def test_transcribe_yields_typed_segments() -> None:
    """ADR-0003: ``transcribe`` MUST yield :class:`TranscribedSegment`
    triples (``start``, ``end``, ``text``) — not the raw library type.
    The Pipeline (POD-008) consumes the abstraction, never the lib.
    """
    canned = [
        _FakeFasterSegment(start=0.0, end=2.5, text="hola"),
        _FakeFasterSegment(start=2.5, end=4.0, text="qué tal"),
    ]
    backend = _make_backend_with_canned_segments(canned)

    out = list(backend.transcribe(_silence_pcm(4.0), lang="es"))

    assert out == [
        TranscribedSegment(start=0.0, end=2.5, text="hola"),
        TranscribedSegment(start=2.5, end=4.0, text="qué tal"),
    ]


def test_transcribe_streams_lazily_per_ADR_0004() -> None:
    """ADR-0004: ``transcribe`` is a streaming contract — segments are
    yielded one-by-one, not buffered. The Pipeline relies on this for
    per-segment progress ticks (POD-013, ADR-0010). Stub the underlying
    iterator so we can assert items arrive incrementally.
    """
    yielded_count = 0

    def _generator() -> Iterator[_FakeFasterSegment]:
        nonlocal yielded_count
        for seg in [
            _FakeFasterSegment(0.0, 1.0, "uno"),
            _FakeFasterSegment(1.0, 2.0, "dos"),
        ]:
            yielded_count += 1
            yield seg

    class _StreamingBackend(FasterWhisperBackend):
        def _build_model(self, model: str, device: str) -> object:
            return object()

        def _run_inference(
            self,
            model: object,
            pcm: npt.NDArray[np.float32],
            lang: str,
        ) -> Iterable[_FakeFasterSegment]:
            return _generator()

    backend = _StreamingBackend()
    backend.load(model="tiny", device="cpu")
    stream = backend.transcribe(_silence_pcm(2.0), lang="es")

    # Pull the first item — only one upstream segment should have been
    # consumed at this point (lazy streaming, not eager buffering).
    first = next(iter(stream))
    assert first.text == "uno"
    assert yielded_count == 1


def test_transcribe_before_load_raises_model_error() -> None:
    """Calling :meth:`transcribe` before :meth:`load` is a programming
    error in the orchestrator (the Pipeline always calls ``load()``
    first per ADR-0009). Surface as :class:`ModelError` rather than a
    ``None``-attribute traceback so the cli's NFR-9 mapping holds.
    """
    backend = FasterWhisperBackend()

    with pytest.raises(ModelError, match="load"):
        list(backend.transcribe(_silence_pcm(1.0), lang="es"))


# ---------------------------------------------------------------------------
# AC-US-5.4 — network unreachable on first run → ModelError exit 5
# ---------------------------------------------------------------------------


def test_load_wraps_network_failure_in_model_error_AC_US_5_4() -> None:
    """AC-US-5.4 (US-5, Must): when the network is unreachable on first
    run and the model is not in the ``huggingface_hub`` cache, the tool
    MUST exit with code 5 and a stderr message naming the model and the
    failure mode. ``cli.py`` translates :class:`ModelError` (exit 5)
    automatically; this test validates the wrap and the message shape.

    ``huggingface_hub`` surfaces a wide vocabulary of network-shaped
    exceptions (``httpx.ConnectError``, ``hf_hub.errors.HfHubHTTPError``,
    raw ``OSError`` for disk / cache, etc.). Any non-``ImportError``
    failure inside ``_build_model`` is wrapped — robust to upstream API
    drift (R-17).
    """
    backend = _make_backend_with_build_error(
        ConnectionError("Failed to resolve 'huggingface.co'"),
    )

    with pytest.raises(ModelError) as exc_info:
        backend.load(model="large-v3", device="cpu")

    msg = str(exc_info.value)
    assert "large-v3" in msg, "ModelError message must name the model (AC-US-5.4)"
    assert "Failed to resolve" in msg or "ConnectionError" in msg, (
        "ModelError message must surface the upstream failure mode (AC-US-5.4)"
    )
    assert isinstance(exc_info.value.__cause__, ConnectionError), (
        "Original exception MUST chain via __cause__ for debuggability"
    )


def test_load_wraps_oserror_disk_failure_in_model_error() -> None:
    """Disk-shaped failures during model resolution (``huggingface_hub``
    cache write, full disk, permission denied) MUST also surface as
    :class:`ModelError` (exit 5). Same family of failures as AC-US-5.4
    but on the local filesystem axis rather than the network.
    """
    backend = _make_backend_with_build_error(
        OSError(28, "No space left on device"),
    )

    with pytest.raises(ModelError) as exc_info:
        backend.load(model="tiny", device="cpu")

    assert isinstance(exc_info.value.__cause__, OSError)
    assert "tiny" in str(exc_info.value)


# ---------------------------------------------------------------------------
# POD-021 — AC-US-5.1 / AC-US-5.2 first-run model-download notice integration
# ---------------------------------------------------------------------------


def _attach_capture(logger_name: str) -> list[logging.LogRecord]:
    """Attach a list-recording handler to ``logger_name`` and return the list.

    Direct handler attach (rather than ``caplog``) so the test does not
    depend on ``propagate`` flags — the backend logs through its own
    module-named child of ``podcast_script``.
    """
    records: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    logger = logging.getLogger(logger_name)
    handler = _Capture()
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    return records


def _make_cache_aware_backend(
    *,
    cached: bool,
    on_build: list[str] | None = None,
) -> FasterWhisperBackend:
    """Build a backend whose ``_is_cached`` is hard-wired to ``cached``.

    ``_build_model`` records its invocation in ``on_build`` (if provided)
    so callers can assert AC-US-5.1's ordering invariant: the notice
    MUST be emitted before any heavy build path runs.
    """

    class _CacheAwareBackend(FasterWhisperBackend):
        def _is_cached(self, model: str) -> bool:
            return cached

        def _build_model(self, model: str, device: str) -> object:
            if on_build is not None:
                on_build.append("build")
            return object()

    return _CacheAwareBackend()


def test_load_emits_first_run_notice_on_cache_miss_AC_US_5_1() -> None:
    """AC-US-5.1: when the model is not in the local cache,
    :meth:`FasterWhisperBackend.load` MUST emit a single
    ``level=info event=model_download model=<name> size_gb=<n>`` line
    (locked shape per ADR-0012) so the user sees within 1 s of process
    start that a multi-GB download is in progress (NFR-6).
    """
    records = _attach_capture("podcast_script.backends.faster")
    backend = _make_cache_aware_backend(cached=False)

    backend.load(model="large-v3", device="cpu")

    notices = [r for r in records if getattr(r, "event", None) == "model_download"]
    assert len(notices) == 1
    notice = notices[0]
    assert notice.levelno == logging.INFO
    assert getattr(notice, "model", None) == "large-v3"
    assert getattr(notice, "size_gb", None) == "3"


def test_load_notice_precedes_build_model_AC_US_5_1() -> None:
    """AC-US-5.1 / NFR-6 ordering invariant: the notice MUST be emitted
    BEFORE :meth:`FasterWhisperBackend._build_model` is called — that
    method is where the heavy ``faster_whisper`` import + HF download
    triggers happen, and the 1-s budget is measured from process start.
    Emitting after the download has begun would defeat the AC.
    """
    records = _attach_capture("podcast_script.backends.faster")
    build_calls: list[str] = []
    notices_at_build_time: list[int] = []

    class _OrderingBackend(FasterWhisperBackend):
        def _is_cached(self, model: str) -> bool:
            return False

        def _build_model(self, model: str, device: str) -> object:
            notices_at_build_time.append(
                sum(1 for r in records if getattr(r, "event", None) == "model_download")
            )
            build_calls.append("build")
            return object()

    _OrderingBackend().load(model="large-v3", device="cpu")

    assert build_calls == ["build"]
    assert notices_at_build_time == [1], (
        "model_download notice must fire BEFORE _build_model so the "
        "AC-US-5.1 1-s budget holds even when HF download is slow"
    )


def test_load_silent_on_cache_hit_AC_US_5_2() -> None:
    """AC-US-5.2: when the requested model is already cached, no
    ``model_download`` notice is emitted. Subsequent runs after the
    initial download stay silent so wrappers piping the tool don't see
    a spurious download event on every invocation.
    """
    records = _attach_capture("podcast_script.backends.faster")
    backend = _make_cache_aware_backend(cached=True)

    backend.load(model="large-v3", device="cpu")

    notices = [r for r in records if getattr(r, "event", None) == "model_download"]
    assert notices == []


def test_load_skips_cache_check_on_repeat_call() -> None:
    """ADR-0011 first-use site: a second :meth:`load` MUST short-circuit
    before the cache check (and before any helper call). Otherwise the
    AC-US-5.2 invariant could be violated for in-process re-use even
    though the model was downloaded by the first call.
    """
    records = _attach_capture("podcast_script.backends.faster")
    cache_calls: list[str] = []

    class _CountingCacheBackend(FasterWhisperBackend):
        def _is_cached(self, model: str) -> bool:
            cache_calls.append(model)
            return False

        def _build_model(self, model: str, device: str) -> object:
            return object()

    backend = _CountingCacheBackend()
    backend.load(model="large-v3", device="cpu")
    backend.load(model="large-v3", device="cpu")

    assert cache_calls == ["large-v3"], "second load() must short-circuit before _is_cached re-runs"
    notices = [r for r in records if getattr(r, "event", None) == "model_download"]
    assert len(notices) == 1


def test_default_is_cached_uses_huggingface_hub_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real ``_is_cached`` path: stub ``huggingface_hub.scan_cache_dir``
    to return a synthetic cache containing ``Systran/faster-whisper-large-v3``
    and assert :meth:`_is_cached` returns ``True`` for ``large-v3`` and
    ``False`` for ``tiny`` (not in the synthetic cache). The real lib is
    consulted only here — POD-030 (Tier 2) covers the live HF surface.
    """

    class _FakeRepo:
        def __init__(self, repo_id: str) -> None:
            self.repo_id = repo_id

    class _FakeCacheInfo:
        def __init__(self, repos: list[_FakeRepo]) -> None:
            self.repos = repos

    fake_cache = _FakeCacheInfo([_FakeRepo("Systran/faster-whisper-large-v3")])

    import huggingface_hub

    def _fake_scan(*_args: Any, **_kwargs: Any) -> _FakeCacheInfo:
        return fake_cache

    monkeypatch.setattr(huggingface_hub, "scan_cache_dir", _fake_scan)

    backend = FasterWhisperBackend()
    assert backend._is_cached("large-v3") is True
    assert backend._is_cached("tiny") is False


@pytest.mark.parametrize(
    ("cached_repo_id", "requested_model", "expected"),
    [
        # Bare model requested, only the .en variant cached: AC-US-5.1
        # would silently regress under a substring match. The matcher
        # MUST anchor on the end of the repo id so this returns False.
        ("Systran/faster-whisper-tiny.en", "tiny", False),
        ("Systran/faster-whisper-base.en", "base", False),
        ("Systran/faster-whisper-small.en", "small", False),
        ("Systran/faster-whisper-medium.en", "medium", False),
        # Same-direction matches MUST stay True — the bare model is
        # cached, requesting it should suppress the notice (AC-US-5.2).
        ("Systran/faster-whisper-tiny", "tiny", True),
        ("Systran/faster-whisper-large-v3", "large-v3", True),
        # Community fork (mobiuslabsgmbh) for large-v3-turbo MUST match;
        # any owner/<faster-whisper-{model}> combination is valid.
        ("mobiuslabsgmbh/faster-whisper-large-v3-turbo", "large-v3-turbo", True),
        # Reverse direction: .en model requested, only bare cached.
        # This correctly returns False under both matchers — the ask
        # really is for a different repo, so the notice should fire.
        ("Systran/faster-whisper-tiny", "tiny.en", False),
    ],
)
def test_default_is_cached_anchors_match_on_end_of_repo_id(
    monkeypatch: pytest.MonkeyPatch,
    cached_repo_id: str,
    requested_model: str,
    expected: bool,
) -> None:
    """Regression for the AC-US-5.1 silent-suppression bug raised on PR #12:
    a substring match (``"faster-whisper-tiny" in "…/faster-whisper-tiny.en"``)
    falsely reports the bare ``tiny`` model as cached when only the
    ``tiny.en`` variant is on disk, suppressing the notice while the
    actual download for ``tiny`` runs unannounced. Anchor the match
    on ``repo.repo_id.endswith(target)`` to disambiguate.
    """

    class _FakeRepo:
        def __init__(self, repo_id: str) -> None:
            self.repo_id = repo_id

    class _FakeCacheInfo:
        def __init__(self, repos: list[_FakeRepo]) -> None:
            self.repos = repos

    import huggingface_hub

    monkeypatch.setattr(
        huggingface_hub,
        "scan_cache_dir",
        lambda *_a, **_k: _FakeCacheInfo([_FakeRepo(cached_repo_id)]),
    )

    assert FasterWhisperBackend()._is_cached(requested_model) is expected


def test_default_is_cached_returns_false_when_scan_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If ``huggingface_hub.scan_cache_dir`` raises (corrupt cache,
    permission denied, etc.), ``_is_cached`` MUST return ``False`` — i.e.
    err on the side of emitting the notice, never silently swallow a
    multi-GB download. False negatives are tolerable; false positives
    are not.
    """
    import huggingface_hub

    def _raising_scan(*_args: Any, **_kwargs: Any) -> Any:
        raise OSError("synthetic scan failure")

    monkeypatch.setattr(huggingface_hub, "scan_cache_dir", _raising_scan)

    assert FasterWhisperBackend()._is_cached("large-v3") is False


# ---------------------------------------------------------------------------
# Issue #44 — silence the ctranslate2 inferred-compute-type warning
# ---------------------------------------------------------------------------


def test_build_model_passes_compute_type_auto_to_whisper_model_issue_44(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Issue #44: ``faster_whisper.WhisperModel(...)``'s default
    ``compute_type="default"`` instructs CTranslate2 to use the saved
    model's compute type (``float16`` on the canonical Systran weights).
    On a target the device cannot natively execute that on (e.g. macOS
    arm64 CPU), CT2 falls back to a supported type AND emits the
    ``[ctranslate2] [warning] The compute type inferred from the saved
    model is float16, but the target device or backend does not support
    efficient float16 computation`` line directly to stderr from the C++
    layer — slipping past the logfmt-only NFR-10 promise.

    Passing ``compute_type="auto"`` makes CT2 pick the most efficient
    natively-supported type for the device without consulting the saved
    type, eliminating the fallback warning. Asserts the kwarg reaches
    the lib constructor verbatim.
    """
    captured: dict[str, Any] = {}

    class _FakeWhisperModel:
        def __init__(self, model: str, **kwargs: Any) -> None:
            captured["model"] = model
            captured.update(kwargs)

    fake_module = types.ModuleType("faster_whisper")
    fake_module.WhisperModel = _FakeWhisperModel  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)

    backend = FasterWhisperBackend()
    backend.load(model="tiny", device="cpu")

    assert captured["model"] == "tiny"
    assert captured["device"] == "cpu"
    assert captured["compute_type"] == "auto", (
        "Issue #44: WhisperModel must be constructed with "
        "compute_type='auto' to silence the CT2 inferred-type fallback "
        "warning on devices that don't natively support the saved "
        "model's compute type"
    )


def test_module_does_not_eagerly_import_huggingface_hub() -> None:
    """ADR-0011: importing :mod:`podcast_script.backends.faster` at CLI
    startup MUST NOT trigger a ``huggingface_hub`` import — the cache
    check is lazy too. Companion to the ``faster_whisper`` lazy-boundary
    test at the top of this file.
    """
    sys.modules.pop("podcast_script.backends.faster", None)
    sys.modules.pop("huggingface_hub", None)

    importlib.import_module("podcast_script.backends.faster")

    assert "huggingface_hub" not in sys.modules

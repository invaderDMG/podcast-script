"""Tests for ``select_backend`` (POD-017 — US-4 / ADR-0003).

The function decides which concrete :class:`WhisperBackend` the cli
composition root instantiates, based on the user's ``--backend`` flag
(possibly ``"auto"``) and the running platform. Two outcomes:

* return a callable that builds a :class:`FasterWhisperBackend` or a
  :class:`MlxWhisperBackend` (POD-019 / POD-020).
* raise :class:`UsageError` (exit 2) when ``--backend mlx-whisper`` is
  used off Apple Silicon — the SRS §6 UC-1 E7 case.

We test the *decision*, not the construction — ``select_backend``
returns the class (or builds an instance via lazy import) and we
verify *which* one. Heavy library imports are still gated by
ADR-0011's lazy-import rule, so the test suite stays Tier 1.
"""

from __future__ import annotations

import sys

import pytest

from podcast_script.backends import base as backends_base
from podcast_script.backends.base import select_backend
from podcast_script.errors import UsageError


def test_auto_on_apple_silicon_returns_mlx(monkeypatch: pytest.MonkeyPatch) -> None:
    """On ``arm64-darwin`` and with ``backend="auto"``, mlx-whisper wins
    per ADR-0003. We monkeypatch :mod:`sys` and :mod:`platform` rather
    than the real platform so the test runs identically on Ubuntu CI.
    """
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(backends_base, "_machine", lambda: "arm64")

    backend = select_backend(backend="auto", device="auto")

    assert backend.name == "mlx-whisper"


def test_auto_off_apple_silicon_returns_faster(monkeypatch: pytest.MonkeyPatch) -> None:
    """Linux/CUDA/CPU, Intel macs, anything that isn't ``arm64-darwin``
    falls through to faster-whisper.
    """
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(backends_base, "_machine", lambda: "x86_64")

    backend = select_backend(backend="auto", device="auto")

    assert backend.name == "faster-whisper"


def test_auto_on_intel_mac_returns_faster(monkeypatch: pytest.MonkeyPatch) -> None:
    """An Intel mac is darwin but not arm64 — stays on faster-whisper.
    Belt-and-braces around the platform-detection rule.
    """
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(backends_base, "_machine", lambda: "x86_64")

    backend = select_backend(backend="auto", device="auto")

    assert backend.name == "faster-whisper"


def test_explicit_faster_whisper_always_returns_faster(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``--backend faster-whisper`` is honored on every platform —
    Apple Silicon users CAN opt into faster-whisper if they want
    portability over speed. The reverse (mlx off arm64) is the only
    illegal pairing per UC-1 E7.
    """
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(backends_base, "_machine", lambda: "arm64")

    backend = select_backend(backend="faster-whisper", device="cpu")

    assert backend.name == "faster-whisper"


def test_explicit_mlx_off_apple_silicon_raises_usage_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UC-1 E7: ``--backend mlx-whisper`` on Linux exits with code 2
    and a stderr message naming the constraint.
    """
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(backends_base, "_machine", lambda: "x86_64")

    with pytest.raises(UsageError) as excinfo:
        select_backend(backend="mlx-whisper", device="auto")

    assert excinfo.value.exit_code == 2
    msg = str(excinfo.value).lower()
    assert "mlx" in msg
    assert "apple silicon" in msg or "arm64" in msg


def test_explicit_mlx_on_apple_silicon_returns_mlx(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(backends_base, "_machine", lambda: "arm64")

    backend = select_backend(backend="mlx-whisper", device="auto")

    assert backend.name == "mlx-whisper"

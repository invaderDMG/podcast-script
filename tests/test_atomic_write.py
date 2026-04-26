"""Tests for the atomic-write helper (POD-009 / ADR-0005).

The helper is the contract that AC-US-6.3 and NFR-5 hang off: writing the
final Markdown must be all-or-nothing. The pipeline orchestrator (POD-008,
SP-2) is the only intended caller; these Tier-1 unit tests pin the
behaviours the orchestrator depends on, so a future refactor cannot
silently drop the atomicity guarantee.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import pytest

from podcast_script.atomic_write import atomic_write


class _Boom(RuntimeError):
    """Sentinel raised by injected failures so tests can assert the leak path."""


def test_atomic_write_writes_complete_content_to_target_NFR_5_success(
    tmp_path: Path,
) -> None:
    """NFR-5 (success path) — when the write completes, the resolved output
    path contains the full content as UTF-8.
    """
    target = tmp_path / "episode.md"
    payload = "# Hola\n\nepisodio de prueba — café ☕\n"

    atomic_write(target, payload)

    assert target.read_text(encoding="utf-8") == payload


def test_atomic_write_preserves_prior_file_on_failure_AC_US_6_3(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC-US-6.3 — if the rename fails after a `--force` run has begun, the
    pre-existing output file at ``path`` is preserved byte-for-byte and no
    stray ``.md.tmp`` remains in the target directory.

    Failure is injected by patching ``os.replace`` so the temp file is
    on disk but the promotion to ``path`` fails — the same window the ADR
    mandates we recover from.
    """
    target = tmp_path / "episode.md"
    prior = "# previous transcript\n\nhand-edited paragraph kept across reruns.\n"
    target.write_text(prior, encoding="utf-8")

    def boom(_src: str | os.PathLike[str], _dst: str | os.PathLike[str]) -> None:
        raise _Boom("simulated FS error during rename")

    monkeypatch.setattr(os, "replace", boom)

    with pytest.raises(_Boom):
        atomic_write(target, "fresh transcript that must not land\n")

    assert target.read_text(encoding="utf-8") == prior
    assert [p.name for p in tmp_path.iterdir()] == [target.name], (
        "no .md.tmp should remain after a cleaned-up failure"
    )


def test_atomic_write_leaves_no_partial_file_on_failure_NFR_5_negative(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NFR-5 (failure path) — when no prior file exists and the rename
    fails, the resolved output path stays absent (no partial Markdown).
    """
    target = tmp_path / "episode.md"
    assert not target.exists()

    def boom(_src: str | os.PathLike[str], _dst: str | os.PathLike[str]) -> None:
        raise _Boom("simulated FS error during rename")

    monkeypatch.setattr(os, "replace", boom)

    with pytest.raises(_Boom):
        atomic_write(target, "should never appear at target\n")

    assert not target.exists()
    assert list(tmp_path.iterdir()) == []


def test_atomic_write_creates_temp_in_target_directory_ADR_0005(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR-0005 — the temp file MUST be created in ``path.parent`` (so the
    rename stays on the same filesystem and remains atomic on POSIX), and
    its name MUST embed ``path.stem`` + the ``.md.tmp`` suffix so a stray
    temp after ``kill -9`` is recognizable to humans.

    Captured via a wrapper around ``tempfile.NamedTemporaryFile`` so the
    assertion is on the kwargs the helper passes, not on observable file
    layout (the temp is unlinked on success or failure, leaving nothing
    to inspect after the call).
    """
    captured: dict[str, Any] = {}
    real_named_temp = tempfile.NamedTemporaryFile

    def spy(*args: Any, **kwargs: Any) -> Any:
        captured.update(kwargs)
        return real_named_temp(*args, **kwargs)

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", spy)

    target = tmp_path / "episode.md"
    atomic_write(target, "ok\n")

    assert captured["dir"] == target.parent
    assert captured["prefix"] == "episode."
    assert captured["suffix"] == ".md.tmp"
    assert captured["delete"] is False

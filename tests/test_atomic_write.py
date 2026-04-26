"""Tests for the atomic-write helper (POD-009 / ADR-0005).

The helper is the contract that AC-US-6.3 and NFR-5 hang off: writing the
final Markdown must be all-or-nothing. The pipeline orchestrator (POD-008,
SP-2) is the only intended caller; these Tier-1 unit tests pin the
behaviours the orchestrator depends on, so a future refactor cannot
silently drop the atomicity guarantee.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from podcast_script import atomic_write as atomic_write_module
from podcast_script.atomic_write import atomic_write


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

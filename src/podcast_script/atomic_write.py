"""Atomic temp-then-rename writer (POD-009 / ADR-0005).

Stub — implementation lands in the green step of the TDD cycle.
"""

from __future__ import annotations

from pathlib import Path


def atomic_write(path: Path, content: str) -> None:
    """Atomically write ``content`` (UTF-8) to ``path``."""
    raise NotImplementedError

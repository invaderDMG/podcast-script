"""Atomic temp-then-rename writer (POD-009 / ADR-0005).

Owns the all-or-nothing write contract behind NFR-5 and AC-US-6.3: the
final Markdown either lands in full at the resolved output path, or the
path stays exactly as it was before the run started. The pipeline
orchestrator (POD-008, SP-2) is the only intended caller.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write(path: Path, content: str) -> None:
    """Atomically write ``content`` (UTF-8) to ``path``.

    A temp file is created in ``path.parent`` (so the rename is on the
    same filesystem and therefore atomic on POSIX per ADR-0005), the
    payload is written and ``fsync``-ed best-effort, then ``os.replace``
    promotes it to ``path``. If anything fails before the rename, the
    temp file is removed and any prior file at ``path`` is untouched.
    """
    payload = content.encode("utf-8")

    tmp = tempfile.NamedTemporaryFile(
        mode="wb",
        dir=path.parent,
        prefix=path.stem + ".",
        suffix=".md.tmp",
        delete=False,
    )
    tmp_path = Path(tmp.name)
    try:
        tmp.write(payload)
        tmp.flush()
        try:
            os.fsync(tmp.fileno())
        except OSError:
            pass
    finally:
        tmp.close()

    os.replace(tmp_path, path)
